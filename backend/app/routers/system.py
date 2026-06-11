from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Device, Rule
from app.schemas import StatsResponse, HealthResponse
from app.services.mqtt_client import mqtt_client

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count(Device.id)))
    online = await session.scalar(
        select(func.count(Device.id)).where(Device.status == "online")
    )
    total_rules = await session.scalar(select(func.count(Rule.id)))
    active_rules = await session.scalar(
        select(func.count(Rule.id)).where(Rule.enabled == 1)
    )
    return StatsResponse(
        device_count=total or 0,
        online_count=online or 0,
        rule_count=total_rules or 0,
        active_rule_count=active_rules or 0,
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", mqtt_connected=mqtt_client.connected)
