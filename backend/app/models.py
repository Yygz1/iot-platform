import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="offline")  # online/offline（连接状态）
    lifecycle = Column(String, nullable=False, default="active")  # pending/active/suspended/decommissioned
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    meta_json = Column("metadata", Text, nullable=False, default="{}")
    registered_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)
    last_seen_at = Column(String, nullable=True)

    shadow = relationship("DeviceShadow", back_populates="device", uselist=False, cascade="all, delete-orphan")


class DeviceShadow(Base):
    __tablename__ = "device_shadows"

    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True)
    reported_state = Column(Text, nullable=False, default="{}")
    desired_state = Column(Text, nullable=False, default="{}")
    version = Column(Integer, nullable=False, default=0)
    updated_at = Column(String, nullable=False, default=_now)

    device = relationship("Device", back_populates="shadow")


class ShadowHistory(Base):
    __tablename__ = "shadow_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    field_path = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    version = Column(Integer, nullable=False)
    changed_at = Column(String, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_shadow_history_device", "device_id", "changed_at"),
    )


class Rule(Base):
    __tablename__ = "rules"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    enabled = Column(Integer, nullable=False, default=1)
    topic_filter = Column(String, nullable=False)
    condition = Column(Text, nullable=True)
    cooldown_seconds = Column(Integer, nullable=False, default=60)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    actions = relationship("RuleAction", back_populates="rule", cascade="all, delete-orphan")


class RuleAction(Base):
    __tablename__ = "rule_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String, nullable=False)
    action_config = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)

    rule = relationship("Rule", back_populates="actions")

    __table_args__ = (
        Index("idx_rule_actions_rule", "rule_id"),
    )


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False, default=_now)
    level = Column(String, nullable=False, default="info")
    source = Column(String, nullable=False)
    device_id = Column(String, nullable=True)
    rule_id = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_event_logs_ts", "timestamp"),
        Index("idx_event_logs_source", "source", "timestamp"),
    )


class RuleExecution(Base):
    __tablename__ = "rule_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String, nullable=True)
    executed_at = Column(String, nullable=False, default=_now)
    match_data = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_rule_executions_lookup", "rule_id", "device_id", "executed_at"),
    )


class AgentStateRecord(Base):
    __tablename__ = "agent_states"

    agent_id = Column(String, primary_key=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)
    current_state = Column(String, nullable=False, default="offline")
    previous_state = Column(String, nullable=True)
    entered_at = Column(String, nullable=False, default=_now)
    context_json = Column(Text, nullable=True)


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=False)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    state_from = Column(String, nullable=False)
    state_to = Column(String, nullable=False)
    trigger = Column(String, nullable=False)
    actions_json = Column(Text, nullable=True)
    timestamp = Column(String, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_agent_decisions_device", "device_id", "timestamp"),
    )


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # dingtalk / wechat / email
    config_json = Column(Text, nullable=False, default="{}")
    enabled = Column(Integer, nullable=False, default=1)
    level = Column(String, nullable=False, default="warning")  # warning / critical
    created_at = Column(String, nullable=False, default=_now)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, nullable=True)
    channel = Column(String, nullable=False)
    device_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    success = Column(Integer, nullable=False, default=0)
    error_msg = Column(Text, nullable=True)
    timestamp = Column(String, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_notification_logs_ts", "timestamp"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=_now)
