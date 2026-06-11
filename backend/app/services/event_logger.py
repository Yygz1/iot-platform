import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog, RuleExecution

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def write_event(
    session: AsyncSession,
    level: str,
    source: str,
    message: str,
    device_id: str | None = None,
    rule_id: str | None = None,
    detail: dict | None = None,
):
    event = EventLog(
        timestamp=_now(),
        level=level,
        source=source,
        device_id=device_id,
        rule_id=rule_id,
        message=message,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
    )
    session.add(event)
    await session.commit()


async def record_execution(
    session: AsyncSession,
    rule_id: str,
    device_id: str | None,
    match_data: dict | None = None,
):
    exec_entry = RuleExecution(
        rule_id=rule_id,
        device_id=device_id,
        executed_at=_now(),
        match_data=json.dumps(match_data, ensure_ascii=False) if match_data else None,
    )
    session.add(exec_entry)
    await session.commit()


async def check_cooldown(
    session: AsyncSession,
    rule_id: str,
    device_id: str | None,
    cooldown_seconds: int,
) -> bool:
    if cooldown_seconds <= 0:
        return True

    from sqlalchemy import select, desc

    stmt = (
        select(RuleExecution)
        .where(
            RuleExecution.rule_id == rule_id,
            RuleExecution.device_id == device_id,
        )
        .order_by(desc(RuleExecution.executed_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    last_exec = result.scalar_one_or_none()

    if last_exec is None:
        return True

    from datetime import timedelta

    last_time = datetime.fromisoformat(last_exec.executed_at)
    if datetime.now(timezone.utc) - last_time > timedelta(seconds=cooldown_seconds):
        return True

    return False
