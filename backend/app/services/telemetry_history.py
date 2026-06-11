"""遥测历史存储 — 内存环形缓冲区，保留每个设备最近 N 条数据"""

import logging
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

MAX_POINTS = 200  # 每个设备保留最近 200 条记录

# {device_id: deque([(timestamp, {field: value}), ...])}
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_POINTS))


def add(device_id: str, data: dict, ts: float | None = None):
    """记录一条遥测数据"""
    ts = ts or time.time()
    _history[device_id].append((ts, dict(data)))


def get_recent(device_id: str, n: int = 20) -> list[dict]:
    """获取最近 n 条记录，返回 [{timestamp, data}, ...]"""
    items = list(_history[device_id])[-n:]
    return [{"timestamp": ts, "data": d} for ts, d in items]


def get_window(device_id: str, minutes: float = 10) -> list[dict]:
    """获取最近 N 分钟内的记录"""
    cutoff = time.time() - minutes * 60
    return [{"timestamp": ts, "data": d} for ts, d in _history[device_id] if ts >= cutoff]


def get_values(device_id: str, field: str, n: int = 20) -> list[float]:
    """获取某个字段最近 n 个数值"""
    items = list(_history[device_id])[-n:]
    return [d.get(field) for _, d in items if field in d and isinstance(d.get(field), (int, float))]


def get_stats(device_id: str, field: str, n: int = 50) -> dict:
    """计算某个字段的统计信息：均值、标准差、最小、最大、斜率"""
    values = get_values(device_id, field, n)
    if len(values) < 2:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "slope": 0, "count": len(values)}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    mn, mx = min(values), max(values)

    # 简单线性回归斜率（y = slope * x + intercept）
    n_pts = len(values)
    x_mean = (n_pts - 1) / 2
    num = sum((i - x_mean) * (v - mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n_pts))
    slope = num / den if den > 0 else 0

    return {"mean": round(mean, 2), "std": round(std, 2),
            "min": round(mn, 2), "max": round(mx, 2),
            "slope": round(slope, 4), "count": n_pts}


def clear(device_id: str):
    """清空某个设备的历史"""
    _history.pop(device_id, None)
