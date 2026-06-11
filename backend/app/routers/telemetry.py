from fastapi import APIRouter, HTTPException

from app.services.telemetry_cache import get_all_telemetry, get_device_telemetry

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("")
async def list_telemetry():
    items = get_all_telemetry()
    return {"items": items, "count": len(items)}


@router.get("/{device_id}")
async def device_telemetry(device_id: str):
    data = get_device_telemetry(device_id)
    if data is None:
        raise HTTPException(status_code=404, detail="设备遥测数据不存在")
    return data
