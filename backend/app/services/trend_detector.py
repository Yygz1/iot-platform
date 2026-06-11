"""趋势检测引擎 — 基于历史数据分析趋势、预测未来值"""

import logging
from dataclasses import dataclass

from app.services.telemetry_history import get_values, get_stats

logger = logging.getLogger(__name__)


@dataclass
class TrendResult:
    slope: float           # 斜率（每采样间隔的变化量）
    direction: str         # "rising" / "falling" / "stable"
    moving_avg: float      # 移动平均
    change_rate: float     # 变化率（最近值 vs N 个点前）
    predicted: float       # 预测值（extrapolate N 步）
    is_anomaly: bool       # 是否异常（偏离均值 > sigma 个标准差）
    confidence: float      # 置信度 0-1


def analyze(device_id: str, field: str, n: int = 20, sigma: float = 2.0) -> TrendResult:
    """分析某个字段的趋势"""
    values = get_values(device_id, field, n)
    if len(values) < 3:
        return TrendResult(
            slope=0, direction="stable", moving_avg=values[-1] if values else 0,
            change_rate=0, predicted=values[-1] if values else 0,
            is_anomaly=False, confidence=0.0,
        )

    stats = get_stats(device_id, field, n)
    current = values[-1]
    slope = stats["slope"]

    # 方向判断（斜率的绝对值小于标准差的 5% 视为平稳）
    threshold = max(stats["std"] * 0.05, 0.01)
    if slope > threshold:
        direction = "rising"
    elif slope < -threshold:
        direction = "falling"
    else:
        direction = "stable"

    # 移动平均
    window = min(10, len(values))
    moving_avg = sum(values[-window:]) / window

    # 变化率（当前值 vs N 步前）
    change_rate = current - values[0]

    # 预测值（线性外推 N 步）
    predicted = current + slope * n

    # 异常检测（当前值偏离均值超过 sigma 个标准差）
    is_anomaly = False
    if stats["std"] > 0:
        z_score = abs(current - stats["mean"]) / stats["std"]
        is_anomaly = z_score > sigma

    # 置信度（基于数据点数量和标准差）
    confidence = min(1.0, len(values) / n) * (1.0 if stats["std"] > 0 else 0.5)

    return TrendResult(
        slope=round(slope, 4),
        direction=direction,
        moving_avg=round(moving_avg, 2),
        change_rate=round(change_rate, 2),
        predicted=round(predicted, 2),
        is_anomaly=is_anomaly,
        confidence=round(confidence, 2),
    )


def trend_slope(device_id: str, field: str, n: int = 20) -> float:
    """返回趋势斜率（供表达式引擎调用）"""
    return analyze(device_id, field, n).slope


def moving_avg(device_id: str, field: str, n: int = 10) -> float:
    """返回移动平均（供表达式引擎调用）"""
    values = get_values(device_id, field, n)
    return round(sum(values) / len(values), 2) if values else 0


def predicted_value(device_id: str, field: str, steps: int = 10) -> float:
    """返回预测值（供表达式引擎调用）"""
    return analyze(device_id, field, max(steps * 2, 20)).predicted


def change_rate(device_id: str, field: str, n: int = 10) -> float:
    """返回变化率（供表达式引擎调用）"""
    return analyze(device_id, field, n).change_rate


def is_anomaly(device_id: str, field: str, sigma: float = 2.0) -> bool:
    """判断当前值是否异常（供表达式引擎调用）"""
    return analyze(device_id, field, sigma=sigma).is_anomaly
