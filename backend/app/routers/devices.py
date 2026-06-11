import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Device, DeviceShadow, ShadowHistory, EventLog
from app.schemas import (
    DeviceCreate,
    DeviceResponse,
    ShadowDocument,
    ShadowState,
    ShadowMetadata,
    ShadowReportedUpdate,
    ShadowDesiredUpdate,
    ShadowDeltaResponse,
)
from app.services.device_shadow import _now, _parse_json, _compute_delta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])

VALID_LIFECYCLE = {"pending", "active", "suspended", "decommissioned"}


class DeviceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    location: str | None = None
    description: str | None = None
    metadata: dict | None = None


class LifecycleUpdate(BaseModel):
    lifecycle: str


def _shadow_doc(device_id: str, row: DeviceShadow) -> ShadowDocument:
    reported = _parse_json(row.reported_state)
    desired = _parse_json(row.desired_state)
    return ShadowDocument(
        device_id=device_id,
        state=ShadowState(reported=reported, desired=desired),
        metadata=ShadowMetadata(
            reported={k: {"timestamp": v} for k, v in reported.get("_timestamps", {}).items()},
            desired={k: {"timestamp": v} for k, v in desired.get("_timestamps", {}).items()},
        ),
        version=row.version,
        timestamp=datetime.now(timezone.utc).timestamp(),
    )


@router.post("", status_code=201, response_model=DeviceResponse)
async def create_device(body: DeviceCreate, session: AsyncSession = Depends(get_session)):
    kwargs = {
        "name": body.name, "type": body.type,
        "meta_json": json.dumps(body.metadata),
        "lifecycle": "active",
    }
    if body.id:
        existing = await session.get(Device, body.id)
        if existing:
            raise HTTPException(status_code=409, detail=f"设备ID '{body.id}' 已存在")
        kwargs["id"] = body.id
    device = Device(**kwargs)
    session.add(device)
    await session.flush()
    shadow = DeviceShadow(device_id=device.id)
    session.add(shadow)
    # 写入创建日志
    session.add(EventLog(timestamp=_now(), level="info", source="device",
                         device_id=device.id, message=f"设备 {device.name} 已创建"))
    await session.commit()
    await session.refresh(device)
    device.meta_json = _parse_json(device.meta_json)
    return device


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    status: str | None = None,
    type: str | None = None,
    lifecycle: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Device)
    if status:
        stmt = stmt.where(Device.status == status)
    if type:
        stmt = stmt.where(Device.type == type)
    if lifecycle:
        stmt = stmt.where(Device.lifecycle == lifecycle)
    stmt = stmt.order_by(Device.registered_at.desc())
    result = await session.execute(stmt)
    devices = result.scalars().all()
    for d in devices:
        d.meta_json = _parse_json(d.meta_json)
    return devices


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, session: AsyncSession = Depends(get_session)):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    device.meta_json = _parse_json(device.meta_json)
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    body: DeviceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新设备信息（name、type、location、description、metadata）"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    if body.name is not None:
        device.name = body.name
    if body.type is not None:
        device.type = body.type
    if body.location is not None:
        device.location = body.location
    if body.description is not None:
        device.description = body.description
    if body.metadata is not None:
        device.meta_json = json.dumps(body.metadata, ensure_ascii=False)

    device.updated_at = _now()
    session.add(EventLog(timestamp=_now(), level="info", source="device",
                         device_id=device_id, message=f"设备信息已更新"))
    await session.commit()
    await session.refresh(device)
    device.meta_json = _parse_json(device.meta_json)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, session: AsyncSession = Depends(get_session)):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 清理 Agent 缓存
    from app.agents.engine import unregister_agent
    unregister_agent(device_id)

    session.add(EventLog(timestamp=_now(), level="warning", source="device",
                         device_id=device_id, message=f"设备 {device.name} 已删除"))
    await session.delete(device)
    await session.commit()


# ── 生命周期管理 ──

@router.put("/{device_id}/lifecycle")
async def update_lifecycle(
    device_id: str,
    body: LifecycleUpdate,
    session: AsyncSession = Depends(get_session),
):
    """修改设备生命周期状态"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    new_lifecycle = body.lifecycle.strip()
    if new_lifecycle not in VALID_LIFECYCLE:
        raise HTTPException(status_code=400, detail=f"无效的生命周期状态: {new_lifecycle}")

    old_lifecycle = device.lifecycle
    if old_lifecycle == new_lifecycle:
        return {"device_id": device_id, "lifecycle": new_lifecycle, "changed": False}

    device.lifecycle = new_lifecycle
    device.updated_at = _now()

    # Agent 生命周期联动
    from app.agents.engine import get_agent, unregister_agent
    from app.agents.state_machine import AgentState

    agent = get_agent(device_id)
    if agent:
        if new_lifecycle == "suspended":
            await agent.evaluate({}, is_online=False)
        elif new_lifecycle == "decommissioned":
            unregister_agent(device_id)
        elif new_lifecycle == "active" and device.status == "online":
            await agent.evaluate({}, is_online=True)

    session.add(EventLog(
        timestamp=_now(), level="info", source="device",
        device_id=device_id,
        message=f"设备生命周期: {old_lifecycle} → {new_lifecycle}",
    ))
    await session.commit()

    return {"device_id": device_id, "lifecycle": new_lifecycle, "changed": True}


@router.post("/{device_id}/enable")
async def enable_device(device_id: str, session: AsyncSession = Depends(get_session)):
    """激活设备（pending/suspended → active）"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.lifecycle == "active":
        return {"device_id": device_id, "lifecycle": "active", "changed": False}
    if device.lifecycle == "decommissioned":
        raise HTTPException(status_code=400, detail="已退役设备不能激活")

    device.lifecycle = "active"
    device.updated_at = _now()
    session.add(EventLog(timestamp=_now(), level="info", source="device",
                         device_id=device_id, message=f"设备已激活"))
    await session.commit()
    return {"device_id": device_id, "lifecycle": "active", "changed": True}


@router.post("/{device_id}/disable")
async def disable_device(device_id: str, session: AsyncSession = Depends(get_session)):
    """禁用设备（active → suspended）"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.lifecycle != "active":
        raise HTTPException(status_code=400, detail="只能禁用 active 状态的设备")

    device.lifecycle = "suspended"
    device.updated_at = _now()

    # Agent 转 OFFLINE
    from app.agents.engine import get_agent
    agent = get_agent(device_id)
    if agent:
        await agent.evaluate({}, is_online=False)

    session.add(EventLog(timestamp=_now(), level="warning", source="device",
                         device_id=device_id, message=f"设备已禁用"))
    await session.commit()
    return {"device_id": device_id, "lifecycle": "suspended", "changed": True}


# ── Shadow endpoints ──

@router.get("/{device_id}/shadow", response_model=ShadowDocument)
async def get_shadow(device_id: str, session: AsyncSession = Depends(get_session)):
    row = await session.get(DeviceShadow, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="影子不存在")
    return _shadow_doc(device_id, row)


@router.put("/{device_id}/shadow/desired", response_model=dict)
async def update_desired(
    device_id: str,
    body: ShadowDesiredUpdate,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(DeviceShadow, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="影子不存在")

    # 过滤掉内部字段（防止 _timestamps 注入）
    clean_state = {k: v for k, v in body.state.items() if not k.startswith("_")}

    desired = _parse_json(row.desired_state)
    for key, val in clean_state.items():
        desired[key] = val
    desired["_timestamps"] = {
        **desired.get("_timestamps", {}),
        **{k: _now() for k in body.state},
    }

    row.desired_state = json.dumps(desired, ensure_ascii=False)
    row.version += 1
    row.updated_at = _now()

    reported = _parse_json(row.reported_state)
    delta = _compute_delta(desired, reported)

    new_version = row.version
    await session.commit()

    if delta:
        from app.services.mqtt_client import mqtt_client
        mqtt_client.publish(
            f"devices/{device_id}/state/delta",
            {"version": new_version, "state": delta, "timestamp": _now()},
        )

    return {"version": new_version, "delta": delta}


@router.put("/{device_id}/shadow/reported", response_model=dict)
async def update_reported(
    device_id: str,
    body: ShadowReportedUpdate,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(DeviceShadow, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="影子不存在")

    # 生命周期检查：只有 active 设备允许上报
    device = await session.get(Device, device_id)
    if device and device.lifecycle != "active":
        raise HTTPException(status_code=403, detail=f"设备生命周期为 {device.lifecycle}，拒绝上报")

    if body.version != row.version:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "version_conflict",
                "current_version": row.version,
                "current": _shadow_doc(device_id, row).model_dump(),
            },
        )

    old_reported = _parse_json(row.reported_state)
    reported = dict(old_reported)

    # 过滤掉内部字段（防止 _timestamps 注入）
    clean_state = {k: v for k, v in body.state.items() if not k.startswith("_")}

    for key, val in clean_state.items():
        reported[key] = val
    reported["_timestamps"] = {
        **reported.get("_timestamps", {}),
        **{k: _now() for k in clean_state},
    }

    desired = _parse_json(row.desired_state)
    for key in clean_state:
        if key in desired:
            old_val = old_reported.get(key)
            history = ShadowHistory(
                device_id=device_id,
                field_path=f"reported.{key}",
                old_value=json.dumps(old_val, ensure_ascii=False) if old_val is not None else None,
                new_value=json.dumps(body.state[key], ensure_ascii=False),
                version=row.version + 1,
            )
            session.add(history)

    row.reported_state = json.dumps(reported, ensure_ascii=False)
    row.version += 1
    row.updated_at = _now()

    if device:
        was_offline = device.status != "online"
        device.last_seen_at = _now()
        if was_offline:
            device.status = "online"
            session.add(EventLog(
                timestamp=_now(), level="info", source="device",
                device_id=device_id, message=f"设备 {device.name} 已上线",
            ))

    new_version = row.version
    await session.commit()

    delta = _compute_delta(desired, reported)
    if delta:
        from app.services.mqtt_client import mqtt_client
        mqtt_client.publish(
            f"devices/{device_id}/state/delta",
            {"version": new_version, "state": delta, "timestamp": _now()},
        )

    return {"version": new_version, "delta": delta}


@router.get("/{device_id}/shadow/delta", response_model=ShadowDeltaResponse)
async def get_delta(device_id: str, session: AsyncSession = Depends(get_session)):
    row = await session.get(DeviceShadow, device_id)
    if not row:
        raise HTTPException(status_code=404, detail="影子不存在")
    desired = _parse_json(row.desired_state)
    reported = _parse_json(row.reported_state)
    delta = _compute_delta(desired, reported)
    return ShadowDeltaResponse(delta=delta, version=row.version)
