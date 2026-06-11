import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import NotificationConfig, NotificationLog
from app.services.device_shadow import _now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    name: str
    channel: str  # dingtalk / wechat / email
    config: dict
    enabled: bool = True
    level: str = "warning"


class NotificationUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None
    level: str | None = None


@router.get("")
async def list_configs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(NotificationConfig).order_by(NotificationConfig.id))
    configs = result.scalars().all()
    return [
        {
            "id": c.id, "name": c.name, "channel": c.channel,
            "config": json.loads(c.config_json),
            "enabled": bool(c.enabled), "level": c.level,
            "created_at": c.created_at,
        }
        for c in configs
    ]


@router.post("", status_code=201)
async def create_config(body: NotificationCreate, session: AsyncSession = Depends(get_session)):
    if body.channel not in ("dingtalk", "wechat", "email"):
        raise HTTPException(status_code=400, detail="无效的渠道类型")
    config = NotificationConfig(
        name=body.name,
        channel=body.channel,
        config_json=json.dumps(body.config, ensure_ascii=False),
        enabled=1 if body.enabled else 0,
        level=body.level,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return {"id": config.id, "name": config.name, "channel": config.channel}


@router.put("/{config_id}")
async def update_config(config_id: int, body: NotificationUpdate,
                        session: AsyncSession = Depends(get_session)):
    config = await session.get(NotificationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    if body.name is not None:
        config.name = body.name
    if body.config is not None:
        config.config_json = json.dumps(body.config, ensure_ascii=False)
    if body.enabled is not None:
        config.enabled = 1 if body.enabled else 0
    if body.level is not None:
        config.level = body.level
    await session.commit()
    return {"id": config.id, "name": config.name, "channel": config.channel}


@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: int, session: AsyncSession = Depends(get_session)):
    config = await session.get(NotificationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    await session.delete(config)
    await session.commit()


@router.post("/{config_id}/test")
async def test_notification(config_id: int, session: AsyncSession = Depends(get_session)):
    config = await session.get(NotificationConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    from app.services.notification import send_notification
    config_data = json.loads(config.config_json)
    title = "🧪 IoT平台通知测试"
    content = "这是一条测试消息，说明通知渠道配置正确。"

    success = await send_notification(config.channel, config_data, title, content)

    # 记录日志
    log = NotificationLog(
        config_id=config.id, channel=config.channel,
        title=title, message=content,
        success=1 if success else 0,
        error_msg=None if success else "测试发送失败",
    )
    session.add(log)
    await session.commit()

    return {"success": success, "channel": config.channel}


@router.get("/log-entries")
async def list_logs(limit: int = Query(default=50, ge=1, le=500), session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(NotificationLog).order_by(desc(NotificationLog.timestamp)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id, "channel": l.channel, "device_id": l.device_id,
            "title": l.title, "message": l.message,
            "success": bool(l.success), "error_msg": l.error_msg,
            "timestamp": l.timestamp,
        }
        for l in logs
    ]
