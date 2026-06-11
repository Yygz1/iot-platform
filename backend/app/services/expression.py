import logging
from functools import partial

from simpleeval import SimpleEval, NameNotDefined

logger = logging.getLogger(__name__)

EXPRESSION_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "type": lambda x: type(x).__name__,
}


class _DotDict(dict):
    def __getattr__(self, name):
        if name in self:
            val = self[name]
            if isinstance(val, dict) and not isinstance(val, _DotDict):
                val = _DotDict(val)
                self[name] = val
            return val
        raise AttributeError(name)


def _make_trend_functions(device_id: str) -> dict:
    """为指定设备创建趋势分析函数（闭包绑定 device_id）"""
    from app.services.trend_detector import (
        trend_slope, moving_avg, predicted_value, change_rate, is_anomaly,
    )
    from app.services.telemetry_history import get_stats

    return {
        "trend": lambda field, n=20: trend_slope(device_id, field, n),
        "moving_avg": lambda field, n=10: moving_avg(device_id, field, n),
        "predicted": lambda field, steps=10: predicted_value(device_id, field, steps),
        "change_rate": lambda field, n=10: change_rate(device_id, field, n),
        "is_anomaly": lambda field, sigma=2.0: is_anomaly(device_id, field, sigma),
        "adaptive_threshold": lambda field, sigma=2.0, default=28.0: _adaptive_threshold(device_id, field, sigma, default),
    }


def _adaptive_threshold(device_id: str, field: str, sigma: float, default: float) -> float:
    """自适应阈值：基于历史均值 + sigma * 标准差，数据不足时回退到默认值"""
    from app.services.telemetry_history import get_stats
    stats = get_stats(device_id, field, n=100)
    if stats["count"] < 10:
        return default
    return round(stats["mean"] + sigma * stats["std"], 2)


def evaluate_condition(expression: str, payload: dict, device_id: str = "") -> bool:
    evaluator = SimpleEval(functions=EXPRESSION_FUNCTIONS)
    evaluator.names["payload"] = _DotDict(payload)

    # 注册趋势函数（需要 device_id）
    if device_id:
        evaluator.names.update(_make_trend_functions(device_id))

    try:
        result = evaluator.eval(expression)
        return bool(result)
    except Exception:
        logger.debug("表达式求值异常", exc_info=True)
        return False
