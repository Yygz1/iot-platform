import json
import logging
import time

logger = logging.getLogger(__name__)

_cache: dict[str, dict] = {}
TTL_SECONDS = 120  # 超过 2 分钟未更新的缓存自动清除


async def on_telemetry(topic: str, payload_str: str):
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "devices" or parts[2] != "telemetry":
        return
    device_id = parts[1]
    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError:
        return
    ts = time.time()
    _cache[device_id] = {
        "device_id": device_id,
        "data": data,
        "timestamp": ts,
    }
    # 同步写入历史记录
    from app.services.telemetry_history import add as history_add
    history_add(device_id, data, ts)
    logger.debug("缓存遥测: %s -> %s", device_id, data)


def _cleanup_expired():
    now = time.time()
    expired = [k for k, v in _cache.items() if now - v["timestamp"] > TTL_SECONDS]
    for k in expired:
        del _cache[k]


def get_all_telemetry() -> list[dict]:
    _cleanup_expired()
    return list(_cache.values())


def get_device_telemetry(device_id: str) -> dict | None:
    return _cache.get(device_id)
