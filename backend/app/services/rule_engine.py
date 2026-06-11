import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models import Rule, RuleAction
from app.services.expression import evaluate_condition
from app.services.event_logger import write_event, record_execution, check_cooldown
from app.services.mqtt_client import mqtt_client

logger = logging.getLogger(__name__)

_rules_cache: list[Rule] = []


async def load_rules():
    global _rules_cache
    async with async_session() as session:
        result = await session.execute(
            select(Rule)
            .where(Rule.enabled == 1)
            .options(selectinload(Rule.actions))
        )
        _rules_cache = list(result.scalars().all())
    logger.info("已加载 %d 条规则", len(_rules_cache))


async def reload_rules():
    await load_rules()


def topic_matches(filter_str: str, topic: str) -> bool:
    pattern = filter_str.replace("+", "[^/]+").replace("#", ".*")
    pattern = f"^{pattern}$"
    return re.match(pattern, topic) is not None


def _extract_device_id(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) >= 2 and parts[0] == "devices":
        return parts[1]
    return None


def _substitute(template: str, payload: dict) -> str:
    """Simple {{variable}} substitution."""
    for key, val in payload.items():
        template = template.replace(f"{{{{payload.{key}}}}}", str(val))
    return template


async def handle_message(topic: str, payload_str: str):
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {}

    device_id = _extract_device_id(topic)

    for rule in _rules_cache:
        if not rule.enabled:
            continue
        if not topic_matches(rule.topic_filter, topic):
            continue

        if rule.condition:
            condition = rule.condition.strip()
            if not evaluate_condition(condition, payload, device_id=device_id or ""):
                continue

        async with async_session() as session:
            if not await check_cooldown(session, rule.id, device_id, rule.cooldown_seconds):
                continue

            match_data = {"topic": topic, "payload": payload}
            await _execute_actions(session, rule, rule.actions, payload, device_id, match_data)


async def _execute_actions(session, rule, actions, payload, device_id, match_data):
    actions_sorted = sorted(actions, key=lambda a: a.order_index)
    for action in actions_sorted:
        try:
            config = json.loads(action.action_config) if isinstance(action.action_config, str) else action.action_config
        except json.JSONDecodeError:
            config = {}

        if action.action_type == "log":
            level = config.get("level", "info")
            template = config.get("message_template", "规则 {rule_name} 触发: {topic}")
            message = template.replace("{rule_name}", rule.name)
            message = message.replace("{topic}", match_data.get("topic", ""))
            message = message.replace("{device_id}", device_id or "")
            for k, v in payload.items():
                message = message.replace(f"{{{k}}}", str(v))
            await write_event(session, level, "rule_engine", message, device_id, rule.id, match_data)

        elif action.action_type == "mqtt_publish":
            topic = config.get("topic", "")
            qos = config.get("qos", 1)
            retain = config.get("retain", False)
            msg = {}
            if "payload_template" in config:
                raw = _substitute(config["payload_template"], payload)
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = raw
            else:
                msg = payload
            mqtt_client.publish(topic, msg if isinstance(msg, dict) else {"message": msg}, qos, retain)

        elif action.action_type == "http_webhook":
            url = config.get("url", "")
            method = config.get("method", "POST").upper()
            body = {}
            if "body_template" in config:
                raw = _substitute(config["body_template"], payload)
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    body = {"raw": raw}
            else:
                body = {"topic": match_data.get("topic"), "payload": payload}

            if url:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=10) as client:
                        if method == "POST":
                            await client.post(url, json=body)
                        elif method == "GET":
                            await client.get(url, params=body)
                        elif method == "PUT":
                            await client.put(url, json=body)
                except Exception:
                    logger.exception("HTTP webhook 调用失败: %s", url)

        elif action.action_type == "set_shadow_desired":
            device_id_action = _substitute(config.get("device_id", ""), payload) or device_id
            shadow_state = config.get("state", {})
            if device_id_action and shadow_state:
                from app.database import async_session as sess_factory
                from app.models import DeviceShadow
                from app.services.device_shadow import _now, _parse_json, _compute_delta

                async with sess_factory() as s:
                    row = await s.get(DeviceShadow, device_id_action)
                    if row:
                        desired = _parse_json(row.desired_state)
                        for k, v in shadow_state.items():
                            desired[k] = v
                        row.desired_state = json.dumps(desired, ensure_ascii=False)
                        row.version += 1
                        row.updated_at = _now()
                        reported = _parse_json(row.reported_state)
                        delta = _compute_delta(desired, reported)
                        await s.commit()
                        if delta:
                            mqtt_client.publish(
                                f"devices/{device_id_action}/state/delta",
                                {"version": row.version, "state": delta, "timestamp": _now()},
                            )

    await record_execution(session, rule.id, device_id, match_data)


async def setup_rule_engine():
    await load_rules()
    mqtt_client.add_handler(handle_message)
