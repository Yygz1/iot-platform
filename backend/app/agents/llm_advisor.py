"""LLM 诊断顾问 — Agent 进入 CRITICAL 状态时自动分析原因

依赖: pip install ollama  (可选，未安装时自动跳过)
"""

import json
import logging

logger = logging.getLogger(__name__)
_ollama_available = None


def _check_ollama() -> bool:
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    try:
        import ollama
        _ollama_available = True
        return True
    except ImportError:
        _ollama_available = False
        logger.info("ollama 未安装，LLM 诊断不可用。安装: pip install ollama")
        return False


async def ask_llm(device_id: str, device_name: str, device_type: str,
                  current_state: str, context: dict) -> str | None:
    """向本地 LLM 请求诊断建议"""
    if not _check_ollama():
        return None

    # 获取近期遥测数据作为上下文
    from app.services.telemetry_cache import get_device_telemetry
    from app.services.telemetry_history import get_recent, get_values, get_stats
    from app.services.trend_detector import analyze as trend_analyze
    telemetry = get_device_telemetry(device_id)

    # 获取趋势分析数据
    trend_info = ""
    if telemetry:
        for field in telemetry.get("data", {}):
            if isinstance(telemetry["data"][field], (int, float)):
                trend = trend_analyze(device_id, field, n=30)
                trend_info += (
                    f"\n  {field}: 当前={telemetry['data'][field]}, "
                    f"均值={trend.moving_avg}, 趋势={trend.direction}({trend.slope}), "
                    f"预测={trend.predicted}, 异常={trend.is_anomaly}"
                )

    # 获取近期决策历史
    from app.database import async_session
    from app.models import AgentDecision
    from sqlalchemy import select, desc
    recent_decisions = []
    try:
        async with async_session() as s:
            result = await s.execute(
                select(AgentDecision)
                .where(AgentDecision.agent_id == device_id)
                .order_by(desc(AgentDecision.timestamp))
                .limit(10)
            )
            recent_decisions = [
                f"{d.state_from}->{d.state_to} ({d.trigger})"
                for d in result.scalars().all()
            ]
    except Exception:
        pass

    prompt = f"""你是一个物联网设备诊断专家。以下设备进入了 CRITICAL 状态，请分析原因并给出排查建议。

设备信息:
- 名称: {device_name}
- 类型: {device_type}
- 当前状态: {current_state}
- 状态转换触发: {context.get('state_from', '?')} -> {context.get('state_to', '?')}

当前遥测数据:
{json.dumps(telemetry.get('data', {}), ensure_ascii=False, indent=2) if telemetry else '暂无'}

趋势分析（移动平均、趋势方向、预测值、是否异常）:
{trend_info if trend_info else '暂无'}

近期状态变更:
{chr(10).join(recent_decisions[:5]) if recent_decisions else '暂无'}

请给出:
1. 可能的原因（最多3条）
2. 建议的排查步骤
3. 是否需要人工介入

用简洁中文回答，每条不超过2行。"""

    try:
        import asyncio, requests
        def _call():
            r = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "qwen2.5:0.5b",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
                timeout=30,
            )
            if r.status_code != 200:
                logger.warning("[LLM] HTTP %d: %s", r.status_code, r.text[:100])
                return None
            return r.json()["message"]["content"]
        answer = await asyncio.to_thread(_call)
        if answer is None:
            return None
        logger.info("[LLM] 诊断完成: %s -> %s", device_id, answer[:100])

        # 写入事件日志
        from app.services.event_logger import write_event
        from app.database import async_session
        async with async_session() as s:
            await write_event(s, "info", "agent",
                              f"[LLM诊断] {device_name}: {answer[:200]}",
                              device_id, detail={"llm_response": answer})
        return answer
    except Exception as e:
        logger.warning("[LLM] 调用失败: %s", e)
        return None
