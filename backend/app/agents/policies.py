"""各设备类型的Agent策略库"""

from app.agents.state_machine import (
    AgentState, TransitionRule, StateAction, StateConfig,
)

# ════════════════════════════════════════════
# 温度传感器 Agent（智能化：自适应阈值 + 趋势预测）
# ════════════════════════════════════════════
TEMPERATURE_TRANSITIONS = [
    TransitionRule(AgentState.NORMAL, AgentState.WARNING,
                   "payload.temperature > adaptive_threshold('temperature', 2, 28) "
                   "or is_anomaly('temperature', 2.0) "
                   "or (trend('temperature') > 0.5 and predicted('temperature', 10) > 35)",
                   confirmations=2, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.CRITICAL,
                   "payload.temperature > adaptive_threshold('temperature', 3, 35) "
                   "or is_anomaly('temperature', 3.0) "
                   "or (trend('temperature') > 1.0 and predicted('temperature', 5) > 40)",
                   confirmations=1, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.NORMAL,
                   "payload.temperature < adaptive_threshold('temperature', 2, 28) "
                   "and trend('temperature') <= 0",
                   confirmations=3, priority=5),
    TransitionRule(AgentState.CRITICAL, AgentState.NORMAL,
                   "payload.temperature < adaptive_threshold('temperature', 2, 28) "
                   "and trend('temperature') <= 0",
                   confirmations=5, priority=5),
]

TEMPERATURE_STATES = [
    StateConfig(AgentState.NORMAL, timeout_seconds=0, on_enter=[
        StateAction("log", {"level": "info", "message": "{agent_name} 温度恢复正常"}),
        StateAction("device_command", {
            "target_device_id": "fan-01",
            "command": {"power": "off"},
            "reason": "温度已恢复正常，关闭风扇",
        }),
    ]),
    StateConfig(AgentState.WARNING, timeout_seconds=1800, on_enter=[  # 30分钟超时升级
        StateAction("log", {"level": "warning", "message": "{agent_name} 温度异常预警!"}),
        StateAction("device_command", {
            "target_device_id": "fan-01",
            "command": {"power": "on", "speed": 3, "cooling_active": True},
            "reason": "温度预警，启动风扇中速降温",
        }),
        StateAction("call_agent", {
            "target_agent_id": "fan-01",
            "request": "request_cooling",
            "message": "温度异常，请求风扇协助降温",
        }),
        StateAction("mqtt_publish", {"topic": "agents/alerts", "qos": 1,
                     "message": "温度预警，已启动风扇降温"}),
    ]),
    StateConfig(AgentState.CRITICAL, timeout_seconds=3600, on_enter=[  # 60分钟超时升级告警
        StateAction("log", {"level": "error", "message": "{agent_name} 温度严重超标!"}),
        StateAction("device_command", {
            "target_device_id": "fan-01",
            "command": {"power": "on", "speed": 5, "cooling_active": True},
            "reason": "温度严重超标，风扇全速运转",
        }),
        StateAction("mqtt_publish", {"topic": "agents/alerts", "qos": 2,
                     "message": "严重高温告警，风扇全速"}),
        StateAction("llm_diagnose", {}),
    ]),
]


# ════════════════════════════════════════════
# 湿度传感器 Agent
# ════════════════════════════════════════════
HUMIDITY_TRANSITIONS = [
    TransitionRule(AgentState.NORMAL, AgentState.WARNING,
                   "payload.humidity < 25 or payload.humidity > 85",
                   confirmations=2, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.CRITICAL,
                   "payload.humidity < 15 or payload.humidity > 95",
                   confirmations=1, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.NORMAL,
                   "payload.humidity > 30 and payload.humidity < 80",
                   confirmations=3, priority=5),
    TransitionRule(AgentState.CRITICAL, AgentState.NORMAL,
                   "payload.humidity > 30 and payload.humidity < 80",
                   confirmations=5, priority=5),
]

HUMIDITY_STATES = [
    StateConfig(AgentState.NORMAL, on_enter=[
        StateAction("log", {"level": "info", "message": "{agent_name} 湿度恢复正常"}),
    ]),
    StateConfig(AgentState.WARNING, on_enter=[
        StateAction("log", {"level": "warning", "message": "{agent_name} 湿度异常预警!"}),
        StateAction("mqtt_publish", {"topic": "agents/alerts", "qos": 1,
                     "message": "湿度异常，检查除湿设备"}),
    ]),
    StateConfig(AgentState.CRITICAL, on_enter=[
        StateAction("log", {"level": "error", "message": "{agent_name} 湿度严重超标!"}),
        StateAction("llm_diagnose", {}),
    ]),
]


# ════════════════════════════════════════════
# 智能灯 Agent
# ════════════════════════════════════════════
SMARTLIGHT_TRANSITIONS = [
    TransitionRule(AgentState.NORMAL, AgentState.WARNING,
                   "payload.brightness < 10",
                   confirmations=2, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.NORMAL,
                   "payload.brightness >= 10",
                   confirmations=3, priority=5),
]

SMARTLIGHT_STATES = [
    StateConfig(AgentState.NORMAL, on_enter=[
        StateAction("log", {"level": "info", "message": "{agent_name} 亮度正常"}),
    ]),
    StateConfig(AgentState.WARNING, on_enter=[
        StateAction("log", {"level": "warning", "message": "{agent_name} 亮度异常偏低!"}),
    ]),
]


# ════════════════════════════════════════════
# 智能风扇 Agent
# ════════════════════════════════════════════
SMARTFAN_TRANSITIONS = [
    TransitionRule(AgentState.NORMAL, AgentState.WARNING,
                   "payload.speed == 0 and payload.power == 'on'",
                   confirmations=2, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.CRITICAL,
                   "payload.mode == 'abnormal'",
                   confirmations=1, priority=10),
    TransitionRule(AgentState.WARNING, AgentState.NORMAL,
                   "payload.speed > 0",
                   confirmations=2, priority=5),
]

SMARTFAN_STATES = [
    StateConfig(AgentState.NORMAL, on_enter=[
        StateAction("log", {"level": "info", "message": "{agent_name} 风扇运行正常"}),
    ]),
    StateConfig(AgentState.WARNING, on_enter=[
        StateAction("log", {"level": "warning", "message": "{agent_name} 风扇已通电但转速为0!"}),
        StateAction("mqtt_publish", {"topic": "agents/alerts", "qos": 1,
                     "message": "风扇故障预警"}),
    ]),
    StateConfig(AgentState.CRITICAL, on_enter=[
        StateAction("log", {"level": "error", "message": "{agent_name} 风扇运行异常!"}),
        StateAction("llm_diagnose", {}),
    ]),
]


# 策略注册表
POLICY_REGISTRY = {
    "temperature_sensor": (TEMPERATURE_TRANSITIONS, TEMPERATURE_STATES),
    "humidity_sensor": (HUMIDITY_TRANSITIONS, HUMIDITY_STATES),
    "smart_light": (SMARTLIGHT_TRANSITIONS, SMARTLIGHT_STATES),
    "smart_fan": (SMARTFAN_TRANSITIONS, SMARTFAN_STATES),
}
