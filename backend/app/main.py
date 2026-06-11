import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update, func

from app.config import settings
from app.database import init_db, async_session
from app.models import Device, EventLog
from app.routers import agents, auth, devices, logs, notifications, rules, system, telemetry
from app.services.mqtt_client import mqtt_client
from app.services.rule_engine import setup_rule_engine
from app.services.telemetry_cache import on_telemetry
from app.utils.logger import setup_logging

from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
# Prometheus 指标定义
# ════════════════════════════════════════════
METRICS_DEVICES_TOTAL = Gauge('iot_devices_total', '设备总数')
METRICS_DEVICES_ONLINE = Gauge('iot_devices_online', '在线设备数')
METRICS_AGENTS = Gauge('iot_agents_by_state', 'Agent状态分布', ['state'])
METRICS_MQTT = Gauge('iot_mqtt_connected', 'MQTT连接状态 1=连接 0=断开')
METRICS_TELEMETRY = Counter('iot_telemetry_total', '遥测数据接收总数', ['device_id'])
METRICS_TRANSITIONS = Counter('iot_agent_transitions_total', 'Agent状态转换总数', ['device_id', 'from_state', 'to_state'])
METRICS_RULE_TRIGGERS = Counter('iot_rule_triggers_total', '规则触发总数', ['rule_id'])

OFFLINE_SECONDS = 60  # 超过此时间未上报视为离线
CHECK_INTERVAL = 15   # 每 15 秒检查一次


async def _agent_evaluate_telemetry(topic: str, payload_str: str):
    """将遥测数据送入Agent状态机评估，首次出现时自动创建Agent"""
    import json as _json
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "devices" or parts[2] != "telemetry":
        return
    device_id = parts[1]
    METRICS_TELEMETRY.labels(device_id=device_id).inc()
    try:
        data = _json.loads(payload_str)
    except Exception:
        return

    from app.agents.engine import get_agent, register_agent, Agent
    from app.agents.policies import POLICY_REGISTRY

    agent = get_agent(device_id)
    if agent is None:
        # 自动创建 Agent：从数据库查设备类型
        async with async_session() as s:
            dev = await s.get(Device, device_id)
            if dev is None:
                return
            policy = POLICY_REGISTRY.get(dev.type)
            if policy is None:
                return  # 无对应策略，不创建
            transitions, states = policy
            agent = Agent(
                device_id=device_id,
                device_name=dev.name,
                device_type=dev.type,
                transitions=transitions,
                states=states,
            )
            register_agent(agent)
            logger.info("[Agent] 已创建: %s (%s)", dev.name, device_id)

    await agent.evaluate(data, is_online=True)


async def _device_offline_checker():
    """后台任务：定期把超时未上报的设备标记为离线，并联动 Agent"""
    while True:
        try:
            async with async_session() as session:
                cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_SECONDS)).isoformat()
                stale = await session.execute(
                    select(Device)
                    .where(Device.status == "online")
                    .where(Device.last_seen_at < cutoff)
                )
                stale_devices = stale.scalars().all()

                if stale_devices:
                    stale_ids = [d.id for d in stale_devices]
                    now_str = datetime.now(timezone.utc).isoformat()
                    for dev in stale_devices:
                        session.add(EventLog(
                            timestamp=now_str, level="warning", source="device",
                            device_id=dev.id, message=f"设备 {dev.name} 已离线（超时未上报）",
                        ))
                        # 联动 Agent 转 OFFLINE
                        from app.agents.engine import get_agent
                        agent = get_agent(dev.id)
                        if agent:
                            await agent.evaluate({}, is_online=False)

                    # 使用设备 ID 列表精确更新，避免误标刚上线的设备
                    await session.execute(
                        update(Device)
                        .where(Device.id.in_(stale_ids))
                        .values(status="offline")
                    )
                    await session.commit()
                    logger.info("已将 %d 台超时设备标记为离线", len(stale_devices))
        except Exception:
            logger.exception("离线检测异常")
        await asyncio.sleep(CHECK_INTERVAL)


async def _restore_agents():
    """从数据库恢复 Agent 状态到内存缓存"""
    from app.agents.engine import Agent, register_agent
    from app.agents.policies import POLICY_REGISTRY
    from app.models import AgentStateRecord

    async with async_session() as s:
        from sqlalchemy import select
        result = await s.execute(select(AgentStateRecord))
        records = result.scalars().all()

    restored = 0
    for rec in records:
        policy = POLICY_REGISTRY.get(rec.device_type)
        if policy is None:
            continue
        transitions, states = policy
        agent = Agent(
            device_id=rec.agent_id,
            device_name=rec.device_name,
            device_type=rec.device_type,
            transitions=transitions,
            states=states,
        )
        # 恢复状态
        from app.agents.state_machine import AgentState
        try:
            agent.current_state = AgentState(rec.current_state)
        except ValueError:
            agent.current_state = AgentState.OFFLINE
        if rec.previous_state:
            try:
                agent.previous_state = AgentState(rec.previous_state)
            except ValueError:
                pass
        agent.state_entered_at = rec.entered_at
        register_agent(agent)
        restored += 1

    if restored:
        logger.info("已从数据库恢复 %d 个 Agent", restored)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("初始化数据库...")
    await init_db()

    # 从数据库恢复 Agent 状态缓存
    await _restore_agents()

    logger.info("连接 MQTT Broker...")
    mqtt_client.connect()
    mqtt_client.subscribe("devices/+/telemetry")
    mqtt_client.subscribe("devices/+/state/reported")
    logger.info("加载规则引擎...")
    mqtt_client.add_handler(on_telemetry)
    mqtt_client.add_handler(_agent_evaluate_telemetry)
    await setup_rule_engine()
    from app.services.agent_bus import setup_agent_bus
    await setup_agent_bus()

    # 启动离线检测任务
    checker_task = asyncio.create_task(_device_offline_checker())
    # 启动指标更新任务
    metrics_task = asyncio.create_task(_update_metrics_loop())

    yield

    logger.info("正在关闭...")
    checker_task.cancel()
    metrics_task.cancel()
    try:
        await checker_task
    except asyncio.CancelledError:
        pass
    try:
        await metrics_task
    except asyncio.CancelledError:
        pass
    await mqtt_client.disconnect()


app = FastAPI(title="IoT 设备影子与规则引擎", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(rules.router)
app.include_router(logs.router)
app.include_router(system.router)
app.include_router(telemetry.router)
app.include_router(agents.router)
app.include_router(notifications.router)


@app.middleware("http")
async def auth_middleware(request, call_next):
    """认证中间件：白名单路径跳过认证，其他路径需要 JWT Token"""
    from app.services.auth import is_whitelisted, verify_token

    path = request.url.path
    method = request.method

    # 白名单路径跳过
    if is_whitelisted(path, method):
        return await call_next(request)

    # 静态资源跳过
    if not path.startswith("/api/"):
        return await call_next(request)

    # 检查 Token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "未登录"})

    token = auth_header[7:]
    user = verify_token(token)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "令牌无效或已过期"})

    return await call_next(request)


@app.get("/")
async def root():
    return {"service": "IoT Platform API", "version": "0.1.0"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def _update_metrics_loop():
    """定期更新 Prometheus Gauge 指标"""
    while True:
        try:
            # 设备数
            async with async_session() as s:
                total = await s.scalar(select(func.count(Device.id)))
                online = await s.scalar(
                    select(func.count(Device.id)).where(Device.status == "online")
                )
            METRICS_DEVICES_TOTAL.set(total or 0)
            METRICS_DEVICES_ONLINE.set(online or 0)

            # Agent 状态分布
            from app.agents.engine import list_agents
            agents_list = list_agents()
            state_counts = {}
            for a in agents_list:
                st = a.get("current_state", "offline")
                state_counts[st] = state_counts.get(st, 0) + 1
            for state in ["offline", "normal", "warning", "critical"]:
                METRICS_AGENTS.labels(state=state).set(state_counts.get(state, 0))

            # MQTT 连接状态
            METRICS_MQTT.set(1 if mqtt_client.connected else 0)
        except Exception:
            logger.debug("指标更新异常", exc_info=True)
        await asyncio.sleep(10)
