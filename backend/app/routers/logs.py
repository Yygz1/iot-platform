from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import EventLog
from app.schemas import LogResponse, LogListResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogListResponse)
async def list_logs(
    level: str | None = None,
    source: str | None = None,
    device_id: str | None = None,
    rule_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(EventLog)
    count_stmt = select(func.count(EventLog.id))

    if level:
        stmt = stmt.where(EventLog.level == level)
        count_stmt = count_stmt.where(EventLog.level == level)
    if source:
        stmt = stmt.where(EventLog.source == source)
        count_stmt = count_stmt.where(EventLog.source == source)
    if device_id:
        stmt = stmt.where(EventLog.device_id == device_id)
        count_stmt = count_stmt.where(EventLog.device_id == device_id)
    if rule_id:
        stmt = stmt.where(EventLog.rule_id == rule_id)
        count_stmt = count_stmt.where(EventLog.rule_id == rule_id)

    total = await session.scalar(count_stmt)
    stmt = stmt.order_by(EventLog.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    items = result.scalars().all()

    return LogListResponse(
        items=[LogResponse.model_validate(item) for item in items],
        total=total or 0,
    )
