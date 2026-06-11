"""因果分析引擎 — Agent 状态转换时自动生成中文解释 + 对话式交互"""

import asyncio
import logging
import time

from app.services.telemetry_history import get_values, get_stats, get_recent
from app.services.trend_detector import analyze as trend_analyze

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════
# 因果分析（状态转换时调用）
# ════════════════════════════════════════════

def analyze_cause(device_id: str, device_type: str,
                  old_state: str, new_state: str,
                  telemetry: dict) -> str:
    """分析状态转换原因，生成中文解释"""
    parts = []
    main_field = _get_main_field(device_type)
    current_val = telemetry.get(main_field, 0)
    unit = _get_unit(device_type)
    field_name = _get_field_name(device_type)

    # 1. 状态转换描述
    state_desc = _describe_transition(old_state, new_state, device_type)
    parts.append(state_desc)

    # 2. 趋势分析
    trend = trend_analyze(device_id, main_field, n=30)
    history_vals = get_values(device_id, main_field, n=30)
    if len(history_vals) >= 3:
        old_val = history_vals[0]
        change = current_val - old_val
        direction = "上升" if change > 0 else "下降" if change < 0 else "持平"
        parts.append(
            f"{field_name}从{old_val}{unit}{direction}至{current_val}{unit}，"
            f"近期斜率{trend.slope:+.3f}/次（{trend.direction}）"
        )

    # 3. 自适应阈值
    stats = get_stats(device_id, main_field, n=100)
    if stats["count"] >= 10:
        adaptive_thresh = round(stats["mean"] + 2 * stats["std"], 2)
        parts.append(
            f"自适应阈值{adaptive_thresh}{unit}（历史均值{stats['mean']}+2σ）"
        )

    # 4. 预测
    if trend.slope != 0 and len(history_vals) >= 5:
        critical = _get_critical_threshold(device_type)
        steps = _steps_to_threshold(current_val, trend.slope, critical)
        if steps > 0:
            minutes = round(steps * 5 / 60, 1)
            if new_state in ("warning", "critical"):
                parts.append(f"按当前趋势约{minutes}分钟后达{round(current_val + trend.slope * steps, 1)}{unit}")

    # 5. 异常检测
    if trend.is_anomaly:
        parts.append("当前值属异常范围（偏离均值>2σ）")

    # 6. 关联事件
    event = _find_correlated_event(device_id, device_type)
    if event:
        parts.append(event)

    return "。".join(parts) + "。"


# ════════════════════════════════════════════
# 对话式交互（/ask 端点调用）
# ════════════════════════════════════════════

async def answer_question(device_id: str, device_type: str, question: str) -> str:
    """回答用户问题，优先 LLM，降级为增强模板"""
    # 意图识别：检查问题是否与设备/IoT相关
    if not _is_relevant_question(question):
        return "我是设备诊断助手，只能回答与设备监控、传感器数据、趋势分析相关的问题。您可以问我：\n• 为什么温度高？\n• 预测趋势？\n• 建议什么操作？\n• 设备状态怎么样？"

    ctx = build_context_for_question(device_id, device_type)

    # 尝试 LLM
    try:
        answer = await _answer_with_llm(ctx, question)
        if answer:
            return answer
    except Exception as e:
        logger.debug("LLM回答失败: %s", e)

    # 降级：增强模板
    return _answer_with_template(ctx, question)


def build_context_for_question(device_id: str, device_type: str) -> dict:
    """收集完整上下文"""
    main_field = _get_main_field(device_type)
    trend = trend_analyze(device_id, main_field, n=30)
    stats = get_stats(device_id, main_field, n=100)
    recent = get_recent(device_id, n=30)

    return {
        "device_id": device_id,
        "device_type": device_type,
        "field_name": _get_field_name(device_type),
        "unit": _get_unit(device_type),
        "current_value": recent[-1]["data"].get(main_field) if recent else None,
        "trend": {
            "slope": trend.slope,
            "direction": trend.direction,
            "moving_avg": trend.moving_avg,
            "predicted": trend.predicted,
            "is_anomaly": trend.is_anomaly,
        },
        "stats": {
            "mean": stats["mean"],
            "std": stats["std"],
            "min": stats["min"],
            "max": stats["max"],
            "count": stats["count"],
        },
        "adaptive_threshold": round(stats["mean"] + 2 * stats["std"], 2) if stats["count"] >= 10 else None,
        "recent_values": [d["data"].get(main_field) for d in recent[-15:] if main_field in d["data"]],
    }


async def _answer_with_llm(ctx: dict, question: str) -> str | None:
    """用 Ollama LLM 回答"""
    import os
    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

    # 检查 Ollama 服务器是否可达
    def _check():
        import requests as _req
        try:
            r = _req.get(f"{ollama_host}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    if not await asyncio.to_thread(_check):
        return None

    prompt = f"""你是物联网设备诊断专家。请根据以下设备数据回答用户问题。

设备: {ctx['device_id']}（{ctx['device_type']}）
监控指标: {ctx['field_name']}
当前值: {ctx['current_value']}{ctx['unit']}
移动均值: {ctx['trend']['moving_avg']}
趋势方向: {ctx['trend']['direction']}（斜率{ctx['trend']['slope']}）
预测值: {ctx['trend']['predicted']}
是否异常: {ctx['trend']['is_anomaly']}
自适应阈值: {ctx['adaptive_threshold']}{ctx['unit']}
历史范围: {ctx['stats']['min']}~{ctx['stats']['max']}（均值{ctx['stats']['mean']}，标准差{ctx['stats']['std']}）
近期数据: {ctx['recent_values']}

用户问题: {question}

如果问题与设备监控、传感器数据、趋势分析无关，请回答"我是设备诊断助手，只能回答与设备监控相关的问题"。
否则请用简洁中文直接回答，不超过100字。不要复述数据，给出分析和判断。"""

    def _call():
        import os
        import requests as _req
        ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        r = _req.post(
            f"{ollama_host}/api/chat",
            json={
                "model": "qwen2.5:0.5b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 200},
            },
            timeout=30,
        )
        if r.status_code != 200:
            return None
        return r.json()["message"]["content"]

    answer = await asyncio.to_thread(_call)
    return answer


def _answer_with_template(ctx: dict, question: str) -> str:
    """增强模板回答"""
    q = question
    field = ctx["field_name"]
    unit = ctx["unit"]
    val = ctx["current_value"]
    if val is None:
        val = "无数据"
    trend = ctx["trend"]
    stats = ctx["stats"]
    thresh = ctx["adaptive_threshold"]

    # ── 趋势类 ──
    if any(k in q for k in ["趋势", "预测", "未来", "将会", "会怎样"]):
        if trend["direction"] == "rising":
            base = f"{field}当前{val}{unit}，持续上升中，斜率{trend['slope']}"
            if trend["predicted"]:
                base += f"，预测值{trend['predicted']}{unit}"
            if trend["is_anomaly"]:
                base += "。注意：已偏离正常范围，需关注"
            return base + "。"
        elif trend["direction"] == "falling":
            return f"{field}当前{val}{unit}，正在下降（斜率{trend['slope']}），移动均值{trend['moving_avg']}。{'趋势向好。' if val and val < trend['moving_avg'] else ''}"
        else:
            return f"{field}当前{val}{unit}，趋势平稳，移动均值{trend['moving_avg']}，无需担心。"

    # ── 原因类 ──
    if any(k in q for k in ["为什么", "原因", "为何", "怎么回事", "怎么了", "发生"]):
        parts = []
        if val and thresh and val > thresh:
            parts.append(f"{field}偏高（{val}{unit}），已超过自适应阈值{thresh}{unit}")
        elif val and stats["min"] and val < stats["min"] * 0.8:
            parts.append(f"{field}偏低（{val}{unit}），低于历史最低值{stats['min']}")
        else:
            parts.append(f"{field}当前{val}{unit}")

        if trend["direction"] == "rising":
            parts.append(f"近期持续上升（斜率{trend['slope']}）")
        elif trend["direction"] == "falling":
            parts.append(f"近期在下降（斜率{trend['slope']}）")

        if trend["is_anomaly"]:
            parts.append("当前值属于异常范围，可能由外部因素或设备故障引起")

        if stats["count"] >= 10:
            parts.append(f"历史正常范围{round(stats['mean']-stats['std'],1)}~{round(stats['mean']+stats['std'],1)}{unit}")

        return "，".join(parts) + "。"

    # ── 建议类 ──
    if any(k in q for k in ["建议", "操作", "怎么办", "处理", "如何", "应该"]):
        if trend["direction"] == "rising" and trend["is_anomaly"]:
            return f"{field}异常上升中，建议：1）检查关联设备（如风扇、空调）是否正常运行 2）检查环境是否有变化（如门窗、热源） 3）如持续恶化需人工排查。"
        elif trend["direction"] == "rising":
            if val and thresh and val > thresh * 0.9:
                return f"{field}接近阈值（当前{val}{unit}，阈值{thresh}{unit}），建议密切关注。系统会在超过阈值时自动触发预警和联动操作。"
            return f"{field}呈上升趋势但尚在安全范围，持续监控即可。"
        elif trend["is_anomaly"]:
            return f"{field}当前值异常，建议检查传感器是否正常、是否有外部干扰。"
        else:
            return f"{field}当前正常（{val}{unit}），趋势平稳，无需操作。"

    # ── 状态类 ──
    if any(k in q for k in ["状态", "情况", "怎么样", "正常吗", "健康"]):
        status = "正常" if not trend["is_anomaly"] else "异常"
        direction_desc = {"rising": "上升中", "falling": "下降中", "stable": "平稳"}
        return f"{field}当前{val}{unit}，状态{status}，趋势{direction_desc.get(trend['direction'], '未知')}。移动均值{trend['moving_avg']}，自适应阈值{thresh}{unit}。"

    # ── 阈值类 ──
    if any(k in q for k in ["阈值", "标准", "范围", "正常范围"]):
        if stats["count"] >= 10:
            return f"自适应阈值为{thresh}{unit}（基于{stats['count']}个历史数据点，均值{stats['mean']}+2×标准差{stats['std']}）。正常范围约{round(stats['mean']-stats['std'],1)}~{round(stats['mean']+stats['std'],1)}{unit}。当前{val}{unit}。"
        return f"历史数据不足，暂使用默认阈值。当前{val}{unit}。"

    # ── 默认：综合报告 ──
    direction_desc = {"rising": "上升", "falling": "下降", "stable": "平稳"}
    return (
        f"{field}当前{val}{unit}，趋势{direction_desc.get(trend['direction'], '未知')}（斜率{trend['slope']}），"
        f"移动均值{trend['moving_avg']}，自适应阈值{thresh}{unit}。"
        f"{'当前值异常，需关注。' if trend['is_anomaly'] else '当前处于正常范围。'}"
    )


# ════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════

def _is_relevant_question(question: str) -> bool:
    """判断问题是否与设备/IoT监控相关"""
    q = question.lower().strip()

    # 太短的问题（<2字符）视为无关
    if len(q) < 2:
        return False

    # IoT/设备相关关键词
    iot_keywords = [
        # 设备相关
        "温度", "湿度", "亮度", "转速", "风扇", "灯", "传感器", "设备",
        "温度计", "空调", "通风", "冷却", "加热", "机器", "服务器",
        # 数据相关
        "数据", "数值", "指标", "读数", "测量", "监控", "曲线", "图表",
        # 趋势相关
        "趋势", "预测", "变化", "上升", "下降", "波动", "异常",
        "均值", "平均", "阈值", "标准差", "范围", "斜率",
        # 状态相关
        "状态", "正常", "异常", "告警", "预警", "故障", "离线", "在线",
        "健康", "情况", "怎么样", "有没有问题",
        # 操作相关
        "建议", "操作", "处理", "排查", "修复", "调整", "维护", "检查",
        # 原因相关
        "为什么", "原因", "怎么回事", "怎么了", "发生", "导致",
        # IoT
        "iot", "mqtt", "agent", "智能体", "设备影子",
        "遥测", "上报", "命令", "控制", "影子",
    ]

    # 明确无关的关键词（直接拒绝）
    irrelevant_keywords = [
        "天气", "新闻", "股票", "电影", "音乐", "游戏", "小说",
        "笑话", "故事", "翻译", "计算", "数学", "编程",
        "你好", "再见", "谢谢", "吃饭", "睡觉", "旅游",
        "hello", "hi", "bye", "thanks",
    ]
    for kw in irrelevant_keywords:
        if kw in q:
            return False

    # 检查是否包含相关关键词
    for kw in iot_keywords:
        if kw in q:
            return True

    # 纯数字或纯符号视为无关
    if all(c.isdigit() or c in ".,!? " for c in q):
        return False

    # 英文问题，检查是否有意义的单词
    english_words = ["what", "why", "how", "when", "temperature", "humidity",
                     "device", "sensor", "status", "trend", "predict", "normal",
                     "abnormal", "alert", "warning", "critical", "value", "data"]
    for w in english_words:
        if w in q:
            return True

    # 其他情况视为无关
    return False


def _get_main_field(device_type: str) -> str:
    return {"temperature_sensor": "temperature", "humidity_sensor": "humidity",
            "smart_light": "brightness", "smart_fan": "speed"}.get(device_type, "temperature")

def _get_field_name(device_type: str) -> str:
    return {"temperature_sensor": "温度", "humidity_sensor": "湿度",
            "smart_light": "亮度", "smart_fan": "转速"}.get(device_type, "数值")

def _get_unit(device_type: str) -> str:
    return {"temperature_sensor": "°C", "humidity_sensor": "%"}.get(device_type, "")

def _get_critical_threshold(device_type: str) -> float:
    return {"temperature_sensor": 35.0, "humidity_sensor": 95.0,
            "smart_light": 10.0, "smart_fan": 5.0}.get(device_type, 100.0)

def _steps_to_threshold(current: float, slope: float, threshold: float) -> int:
    if slope == 0:
        return 0
    steps = (threshold - current) / slope
    return max(0, int(steps))

def _find_correlated_event(device_id: str, device_type: str) -> str | None:
    try:
        main_field = _get_main_field(device_type)
        recent = get_recent(device_id, n=60)
        if len(recent) < 10:
            return None
        vals = [d["data"].get(main_field) for d in recent if main_field in d["data"]]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if len(vals) < 10:
            return None
        max_change = 0
        change_idx = 0
        for i in range(1, len(vals)):
            change = abs(vals[i] - vals[i-1])
            if change > max_change:
                max_change = change
                change_idx = i
        mean_val = sum(vals) / len(vals)
        if max_change > mean_val * 0.3 and max_change > 2:
            before = vals[change_idx - 1]
            after = vals[change_idx]
            direction = "骤升" if after > before else "骤降"
            return f"检测到数据{direction}（{before}→{after}），可能存在外部干预"
        return None
    except Exception:
        return None

def _describe_transition(old_state: str, new_state: str, device_type: str) -> str:
    transitions = {
        ("normal", "warning"): "设备进入预警状态",
        ("normal", "critical"): "设备直接进入告警状态",
        ("warning", "critical"): "预警升级为告警",
        ("warning", "normal"): "设备恢复正常",
        ("critical", "normal"): "设备从告警状态恢复",
        ("offline", "normal"): "设备上线",
        ("normal", "offline"): "设备离线",
    }
    return transitions.get((old_state, new_state), f"状态从{old_state}变为{new_state}")
