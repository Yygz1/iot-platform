import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import AgentDecision, AgentStateRecord
from app.schemas import AgentSnapshot, AgentDecisionResponse
from app.agents.engine import list_agents, get_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentSnapshot])
async def get_agents():
    return list_agents()


@router.get("/{agent_id}/state", response_model=AgentSnapshot)
async def get_agent_state(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return agent.snapshot()


@router.get("/{agent_id}/decisions", response_model=list[AgentDecisionResponse])
async def get_agent_decisions(agent_id: str, limit: int = 50,
                              session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AgentDecision)
        .where(AgentDecision.agent_id == agent_id)
        .order_by(desc(AgentDecision.timestamp))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{agent_id}/trend")
async def get_agent_trend(agent_id: str):
    """获取 Agent 的趋势分析数据"""
    from app.services.trend_detector import analyze
    from app.services.telemetry_cache import get_device_telemetry

    telemetry = get_device_telemetry(agent_id)
    if not telemetry:
        return {"device_id": agent_id, "fields": {}}

    fields = {}
    for field, value in telemetry.get("data", {}).items():
        if isinstance(value, (int, float)):
            trend = analyze(agent_id, field, n=30)
            fields[field] = {
                "current": value,
                "moving_avg": trend.moving_avg,
                "slope": trend.slope,
                "direction": trend.direction,
                "predicted": trend.predicted,
                "change_rate": trend.change_rate,
                "is_anomaly": trend.is_anomaly,
                "confidence": trend.confidence,
            }

    return {"device_id": agent_id, "fields": fields}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("/{agent_id}/ask")
async def ask_agent(agent_id: str, body: AskRequest):
    """与 Agent 对话：提问并获得智能回答"""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")

    from app.services.causal_analyzer import answer_question
    answer = await answer_question(agent_id, agent.device_type, question)

    return {"agent_id": agent_id, "question": question, "answer": answer}
