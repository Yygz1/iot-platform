import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Rule, RuleAction
from app.schemas import (
    RuleCreate,
    RuleUpdate,
    RuleToggle,
    RuleResponse,
    RuleActionResponse,
)
from app.services.rule_engine import reload_rules

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules", tags=["rules"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_response(rule: Rule) -> RuleResponse:
    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description or "",
        enabled=bool(rule.enabled),
        topic_filter=rule.topic_filter,
        condition=rule.condition,
        cooldown_seconds=rule.cooldown_seconds,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        actions=[
            RuleActionResponse(
                id=a.id,
                action_type=a.action_type,
                action_config=json.loads(a.action_config) if isinstance(a.action_config, str) else a.action_config,
                order_index=a.order_index,
            )
            for a in (rule.actions or [])
        ],
    )


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    enabled: bool | None = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Rule).options(selectinload(Rule.actions))
    if enabled is not None:
        stmt = stmt.where(Rule.enabled == (1 if enabled else 0))
    stmt = stmt.order_by(Rule.created_at.desc())
    result = await session.execute(stmt)
    rules = result.scalars().all()
    return [_model_to_response(r) for r in rules]


@router.post("", status_code=201, response_model=RuleResponse)
async def create_rule(body: RuleCreate, session: AsyncSession = Depends(get_session)):
    rule = Rule(
        name=body.name,
        description=body.description,
        topic_filter=body.topic_filter,
        condition=body.condition,
        cooldown_seconds=body.cooldown_seconds,
    )
    session.add(rule)
    await session.flush()

    for action in body.actions:
        ra = RuleAction(
            rule_id=rule.id,
            action_type=action.action_type,
            action_config=json.dumps(action.action_config, ensure_ascii=False),
            order_index=action.order_index,
        )
        session.add(ra)

    await session.commit()
    await session.refresh(rule)
    await reload_rules()

    result = await session.execute(
        select(Rule).where(Rule.id == rule.id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one()
    return _model_to_response(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return _model_to_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, body: RuleUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    rule.name = body.name
    rule.description = body.description
    rule.topic_filter = body.topic_filter
    rule.condition = body.condition
    rule.cooldown_seconds = body.cooldown_seconds
    rule.updated_at = _now()

    for existing in rule.actions:
        await session.delete(existing)
    await session.flush()

    for action in body.actions:
        ra = RuleAction(
            rule_id=rule.id,
            action_type=action.action_type,
            action_config=json.dumps(action.action_config, ensure_ascii=False),
            order_index=action.order_index,
        )
        session.add(ra)

    await session.commit()
    await reload_rules()

    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one()
    return _model_to_response(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, session: AsyncSession = Depends(get_session)):
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    await session.delete(rule)
    await session.commit()
    await reload_rules()


@router.post("/{rule_id}/toggle", response_model=RuleResponse)
async def toggle_rule(rule_id: str, body: RuleToggle, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    rule.enabled = 1 if body.enabled else 0
    rule.updated_at = _now()
    await session.commit()
    await reload_rules()

    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.actions))
    )
    rule = result.scalar_one()
    return _model_to_response(rule)
