import asyncio
import json
import logging
from datetime import datetime, timezone

from app.agents.state_machine import (
    AgentState, ALLOWED, TransitionRule, StateConfig, CONFIRMATION_LIMIT,
)
from app.models import AgentStateRecord, AgentDecision
from app.database import async_session

logger = logging.getLogger(__name__)

_confirm_counters: dict[str, dict[str, int]] = {}  # agent_id -> {transition_key: count}
_agent_cache: dict[str, "Agent"] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Agent:
    def __init__(self, device_id: str, device_name: str, device_type: str,
                 transitions: list[TransitionRule], states: list[StateConfig]):
        self.device_id = device_id
        self.device_name = device_name
        self.device_type = device_type
        self.transitions = sorted(transitions, key=lambda t: -t.priority)
        self.states: dict[AgentState, StateConfig] = {s.state: s for s in states}
        self.current_state = AgentState.OFFLINE
        self.previous_state: AgentState | None = None
        self.state_entered_at = _now()

    async def evaluate(self, telemetry: dict, is_online: bool):
        if is_online and self.current_state == AgentState.OFFLINE:
            await self._transition_to(AgentState.NORMAL, "设备上线")
            return
        if not is_online and self.current_state != AgentState.OFFLINE:
            await self._transition_to(AgentState.OFFLINE, "设备离线")
            return
        if self.current_state == AgentState.OFFLINE:
            return

        # 超时自动转换
        await self._check_timeout()

        for rule in self.transitions:
            if rule.source != self.current_state:
                continue
            if self.current_state not in ALLOWED or rule.target not in ALLOWED.get(self.current_state, set()):
                continue

            matched = False
            if not rule.condition:
                matched = True
            else:
                from app.services.expression import evaluate_condition
                matched = evaluate_condition(rule.condition, telemetry, device_id=self.device_id)

            tkey = f"{rule.source.value}->{rule.target.value}"
            if matched:
                c = _confirm_counters.get(self.device_id, {}).get(tkey, 0) + 1
                _confirm_counters.setdefault(self.device_id, {})[tkey] = min(c, CONFIRMATION_LIMIT)
                if c >= rule.confirmations:
                    await self._transition_to(rule.target, f"条件满足: {rule.condition}")
                    _confirm_counters[self.device_id][tkey] = 0
            else:
                _confirm_counters.setdefault(self.device_id, {})[tkey] = 0

    async def _check_timeout(self):
        """检查当前状态是否超时，自动升级"""
        cfg = self.states.get(self.current_state)
        if not cfg or cfg.timeout_seconds <= 0:
            return
        from datetime import datetime, timezone
        try:
            entered = datetime.fromisoformat(self.state_entered_at)
            elapsed = (datetime.now(timezone.utc) - entered).total_seconds()
            if elapsed >= cfg.timeout_seconds:
                # 超时：尝试升级到更严重状态
                escalation = {
                    AgentState.NORMAL: AgentState.WARNING,
                    AgentState.WARNING: AgentState.CRITICAL,
                }
                target = escalation.get(self.current_state)
                if target and target in ALLOWED.get(self.current_state, set()):
                    await self._transition_to(target, f"状态超时 ({int(elapsed)}秒)")
        except Exception:
            logger.debug("超时检查异常", exc_info=True)

    async def _transition_to(self, target: AgentState, trigger: str):
        if target not in ALLOWED.get(self.current_state, set()):
            return

        old_state = self.current_state

        # 生成因果分析解释
        try:
            from app.services.causal_analyzer import analyze_cause
            from app.services.telemetry_cache import get_device_telemetry
            telemetry_data = get_device_telemetry(self.device_id)
            if telemetry_data and target != AgentState.OFFLINE:
                cause = analyze_cause(
                    self.device_id, self.device_type,
                    old_state.value, target.value,
                    telemetry_data.get("data", {}),
                )
                trigger = cause
        except Exception:
            pass  # 因果分析失败不影响状态转换
        self.previous_state = old_state
        self.current_state = target
        self.state_entered_at = _now()

        old_cfg = self.states.get(old_state)
        new_cfg = self.states.get(target)

        # exit actions
        if old_cfg:
            for action in old_cfg.on_exit:
                await self._execute_action(action, {"state_from": old_state.value, "state_to": target.value})

        # entry actions
        if new_cfg:
            for action in new_cfg.on_enter:
                await self._execute_action(action, {"state_from": old_state.value, "state_to": target.value})

        # 记录决策
        await self._log_decision(old_state, target, trigger)

        # MQTT 广播状态变更
        try:
            from app.services.mqtt_client import mqtt_client
            mqtt_client.publish(f"agents/{self.device_id}/state", {
                "device_id": self.device_id,
                "state": target.value,
                "previous": old_state.value,
                "trigger": trigger,
                "timestamp": _now(),
            })
        except Exception:
            logger.exception("Agent状态广播失败")

        logger.info("[%s] %s: %s -> %s (trigger: %s)",
                     self.device_id, self.device_name, old_state.value, target.value, trigger)

        # 告警通知（WARNING/CRITICAL 时触发）
        if target in (AgentState.WARNING, AgentState.CRITICAL):
            asyncio.create_task(self._send_alert(old_state, target, trigger))

    async def _execute_action(self, action, context: dict):
        try:
            if action.action_type == "log":
                await self._action_log(action, context)
            elif action.action_type == "mqtt_publish":
                await self._action_mqtt(action, context)
            elif action.action_type == "call_agent":
                await self._action_call_agent(action, context)
            elif action.action_type == "device_command":
                await self._action_device_command(action, context)
            elif action.action_type == "llm_diagnose":
                await self._action_llm(action, context)
        except Exception:
            logger.exception("Agent动作执行异常: %s", action.action_type)

    async def _send_alert(self, old_state: AgentState, new_state: AgentState, trigger: str):
        """发送告警通知"""
        try:
            from app.services.notification import send_notification, format_alert_message
            from app.services.trend_detector import analyze as trend_analyze
            from app.models import NotificationConfig, NotificationLog
            from sqlalchemy import select

            # 获取趋势信息
            from app.services.telemetry_cache import get_device_telemetry
            telemetry = get_device_telemetry(self.device_id)
            trend_info = None
            if telemetry:
                from app.services.telemetry_history import get_values
                main_field = {"temperature_sensor": "temperature", "humidity_sensor": "humidity",
                              "smart_light": "brightness", "smart_fan": "speed"}.get(self.device_type, "temperature")
                trend = trend_analyze(self.device_id, main_field, n=20)
                trend_info = {"direction": trend.direction, "slope": trend.slope,
                              "predicted": trend.predicted, "is_anomaly": trend.is_anomaly}

            title, content = format_alert_message(
                self.device_name, self.device_id,
                old_state.value, new_state.value, trigger, trend_info,
            )

            # 查询启用的通知配置
            async with async_session() as s:
                result = await s.execute(
                    select(NotificationConfig).where(NotificationConfig.enabled == 1)
                )
                configs = result.scalars().all()

                for cfg in configs:
                    # 检查级别过滤
                    if cfg.level == "critical" and new_state != AgentState.CRITICAL:
                        continue

                    config_data = json.loads(cfg.config_json)
                    success = await send_notification(cfg.channel, config_data, title, content)

                    # 记录通知日志
                    log = NotificationLog(
                        config_id=cfg.id, channel=cfg.channel,
                        device_id=self.device_id, title=title, message=content,
                        success=1 if success else 0,
                        error_msg=None if success else "发送失败",
                    )
                    s.add(log)
                await s.commit()
        except Exception:
            logger.exception("告警通知发送异常")

    async def _action_log(self, action, context: dict):
        from app.services.event_logger import write_event
        level = action.config.get("level", "info")
        template = action.config.get("message", "Agent {agent_name}: {state_from} -> {state_to}")
        msg = template.format(
            agent_name=self.device_name,
            state_from=context.get("state_from", ""),
            state_to=context.get("state_to", ""),
        )
        async with async_session() as s:
            await write_event(s, level, "agent", msg, self.device_id)

    async def _action_mqtt(self, action, context: dict):
        from app.services.mqtt_client import mqtt_client
        topic = action.config.get("topic", f"agents/{self.device_id}/alert")
        qos = action.config.get("qos", 1)
        payload = {
            "agent_id": self.device_id,
            "agent_name": self.device_name,
            "state": self.current_state.value,
            "message": action.config.get("message", ""),
            "timestamp": _now(),
        }
        mqtt_client.publish(topic, payload, qos)

    async def _action_call_agent(self, action, context: dict):
        from app.services.mqtt_client import mqtt_client
        target_id = action.config.get("target_agent_id", "")
        if not target_id:
            return
        topic = f"agents/{self.device_id}/request/{target_id}"
        payload = {
            "requester_id": self.device_id,
            "requester_name": self.device_name,
            "request": action.config.get("request", ""),
            "message": action.config.get("message", ""),
            "timestamp": _now(),
        }
        mqtt_client.publish(topic, payload, qos=1)
        logger.info("[%s] 协作请求 -> %s: %s", self.device_id, target_id,
                     action.config.get("request", ""))

    async def _action_device_command(self, action, context: dict):
        from app.services.mqtt_client import mqtt_client
        target_id = action.config.get("target_device_id", "")
        command = action.config.get("command", {})
        if not target_id or not command:
            return
        topic = f"devices/{target_id}/commands"
        payload = {
            **command,
            "source_agent": self.device_id,
            "reason": action.config.get("reason", ""),
            "timestamp": _now(),
        }
        mqtt_client.publish(topic, payload, qos=1)
        logger.info("[%s] 设备命令 -> %s: %s", self.device_id, target_id, command)

    async def _action_llm(self, action, context: dict):
        try:
            from app.agents.llm_advisor import ask_llm
            await ask_llm(self.device_id, self.device_name, self.device_type,
                          self.current_state.value, context)
        except ImportError:
            logger.debug("LLM未配置，跳过")
        except Exception:
            logger.exception("LLM调用异常")

    async def _log_decision(self, old_state: AgentState, target: AgentState, trigger: str):
        async with async_session() as s:
            dec = AgentDecision(
                agent_id=self.device_id,
                device_id=self.device_id,
                state_from=old_state.value,
                state_to=target.value,
                trigger=trigger,
                timestamp=_now(),
            )
            s.add(dec)

            # upsert AgentStateRecord
            from sqlalchemy import select
            rec = await s.scalar(select(AgentStateRecord).where(AgentStateRecord.agent_id == self.device_id))
            if rec:
                rec.current_state = target.value
                rec.previous_state = old_state.value
                rec.entered_at = _now()
            else:
                s.add(AgentStateRecord(
                    agent_id=self.device_id,
                    device_id=self.device_id,
                    device_name=self.device_name,
                    device_type=self.device_type,
                    current_state=target.value,
                    previous_state=old_state.value,
                    entered_at=_now(),
                ))
            await s.commit()

    def snapshot(self) -> dict:
        cfg = self.states.get(self.current_state)
        return {
            "agent_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "current_state": self.current_state.value,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "entered_at": self.state_entered_at,
            "timeout_seconds": cfg.timeout_seconds if cfg else 0,
        }


def get_agent(device_id: str) -> Agent | None:
    return _agent_cache.get(device_id)


def register_agent(agent: Agent):
    _agent_cache[agent.device_id] = agent


def unregister_agent(device_id: str):
    _agent_cache.pop(device_id, None)


def list_agents() -> list[dict]:
    return [a.snapshot() for a in _agent_cache.values()]
