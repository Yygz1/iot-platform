"""Agent 间 MQTT 通信总线"""

import json
import logging
from app.services.mqtt_client import mqtt_client

logger = logging.getLogger(__name__)


async def handle_agent_message(topic: str, payload_str: str):
    """处理 Agent 间通信消息"""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return

    parts = topic.split("/")

    # agents/{requester_id}/request/{target_id}  → 转发协作请求
    if len(parts) == 4 and parts[0] == "agents" and parts[2] == "request":
        requester_id = parts[1]
        target_id = parts[3]
        logger.info("[AgentBus] 协作请求 %s -> %s: %s", requester_id, target_id,
                     payload.get("request", ""))
        await _handle_collaboration_request(requester_id, target_id, payload)

    # agents/{responder_id}/respond/{requester_id}  → 处理协作响应
    elif len(parts) == 4 and parts[0] == "agents" and parts[2] == "respond":
        responder_id = parts[1]
        requester_id = parts[3]
        logger.info("[AgentBus] 协作响应 %s -> %s: %s", responder_id, requester_id,
                     payload.get("response", ""))
        await _handle_collaboration_response(responder_id, requester_id, payload)

    elif topic == "agents/broadcast":
        logger.info("[AgentBus] 广播: %s", payload.get("request", ""))


async def _handle_collaboration_request(requester_id: str, target_id: str, payload: dict):
    """处理协作请求：温度Agent请求风扇Agent加速等"""
    from app.agents.engine import get_agent
    agent = get_agent(target_id)
    if agent is None:
        logger.warning("[AgentBus] 目标Agent %s 不存在，跳过", target_id)
        return

    request = payload.get("request", "")
    request_lower = request.lower()

    # 风扇设备：收到降温请求 → 开机
    if agent.device_type == "smart_fan" and "cooling" in request_lower:
        mqtt_client.publish(f"devices/{target_id}/commands", {
            "power": "on",
            "speed": 3,
            "source_agent": requester_id,
            "reason": f"协作请求: {requester_id} 请求降温",
        })
        mqtt_client.publish(f"agents/{target_id}/respond/{requester_id}", {
            "responder_id": target_id,
            "responder_name": agent.device_name,
            "response": "已启动风扇，转速3",
            "action_taken": "fan_on",
            "timestamp": payload.get("timestamp", ""),
        })
        await _log_collaboration(requester_id, target_id, request, "风扇已启动，转速3")
        logger.info("[AgentBus] %s 响应 %s: 风扇已启动", target_id, requester_id)

    # 灯光设备：收到降温请求 → 降低亮度减少发热
    elif agent.device_type == "smart_light" and "cooling" in request_lower:
        mqtt_client.publish(f"devices/{target_id}/commands", {
            "brightness": 25,
            "source_agent": requester_id,
            "reason": f"协作请求: {requester_id} 请求降温，降低亮度",
        })
        mqtt_client.publish(f"agents/{target_id}/respond/{requester_id}", {
            "responder_id": target_id,
            "responder_name": agent.device_name,
            "response": "已降低亮度至25%",
            "action_taken": "dim_light",
            "timestamp": payload.get("timestamp", ""),
        })
        await _log_collaboration(requester_id, target_id, request, "灯光亮度已降低至25%")
        logger.info("[AgentBus] %s 响应 %s: 降低亮度", target_id, requester_id)

    # 通用响应：未知请求类型
    else:
        logger.info("[AgentBus] %s 收到请求但无匹配动作: %s", target_id, request)


async def _handle_collaboration_response(responder_id: str, requester_id: str, payload: dict):
    """处理协作响应：记录协作结果"""
    response = payload.get("response", "")
    action = payload.get("action_taken", "")
    await _log_collaboration(responder_id, requester_id, f"响应: {response}", action)
    logger.info("[AgentBus] 协作完成: %s -> %s (%s)", responder_id, requester_id, response)


async def _log_collaboration(from_id: str, to_id: str, action: str, result: str):
    """记录协作事件到事件日志"""
    try:
        from app.services.event_logger import write_event
        from app.database import async_session
        async with async_session() as s:
            await write_event(
                s, "info", "agent_collaboration",
                f"Agent协作: {from_id} → {to_id} | {action} | 结果: {result}",
                from_id,
                detail={"from": from_id, "to": to_id, "action": action, "result": result},
            )
    except Exception:
        logger.exception("记录协作事件失败")


async def setup_agent_bus():
    mqtt_client.add_handler(handle_agent_message)
    mqtt_client.subscribe("agents/+/request/+")
    mqtt_client.subscribe("agents/+/respond/+")
    mqtt_client.subscribe("agents/broadcast")
    logger.info("[AgentBus] Agent 通信总线已启动（含协作响应）")
