from typing import Literal
from pydantic import BaseModel, Field


# ── Device ──

class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["temperature_sensor", "humidity_sensor", "smart_light", "smart_fan"]
    metadata: dict = Field(default_factory=dict)
    id: str | None = None


class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    status: str
    lifecycle: str = "active"
    location: str | None = None
    description: str | None = None
    meta_json: dict = Field(serialization_alias="metadata")
    registered_at: str
    updated_at: str | None = None
    last_seen_at: str | None = None

    model_config = {"from_attributes": True}


# ── Shadow ──

class ShadowState(BaseModel):
    reported: dict = Field(default_factory=dict)
    desired: dict = Field(default_factory=dict)


class ShadowMetadata(BaseModel):
    reported: dict = Field(default_factory=dict)
    desired: dict = Field(default_factory=dict)


class ShadowDocument(BaseModel):
    device_id: str
    state: ShadowState
    metadata: ShadowMetadata
    version: int
    timestamp: float


class ShadowReportedUpdate(BaseModel):
    state: dict
    version: int


class ShadowDesiredUpdate(BaseModel):
    state: dict


class ShadowDeltaResponse(BaseModel):
    delta: dict
    version: int


# ── Rule ──

class RuleActionCreate(BaseModel):
    action_type: str
    action_config: dict = Field(default_factory=dict)
    order_index: int = 0


class RuleActionResponse(BaseModel):
    id: int
    action_type: str
    action_config: dict
    order_index: int

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    name: str
    description: str = ""
    topic_filter: str
    condition: str | None = None
    cooldown_seconds: int = 60
    actions: list[RuleActionCreate] = Field(default_factory=list)


class RuleUpdate(BaseModel):
    name: str
    description: str = ""
    topic_filter: str
    condition: str | None = None
    cooldown_seconds: int = 60
    actions: list[RuleActionCreate] = Field(default_factory=list)


class RuleToggle(BaseModel):
    enabled: bool


class RuleResponse(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    topic_filter: str
    condition: str | None = None
    cooldown_seconds: int
    created_at: str
    updated_at: str
    actions: list[RuleActionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── Log ──

class LogResponse(BaseModel):
    id: int
    timestamp: str
    level: str
    source: str
    device_id: str | None = None
    rule_id: str | None = None
    message: str
    detail: str | None = None

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    items: list[LogResponse]
    total: int


# ── Stats ──

class StatsResponse(BaseModel):
    device_count: int
    online_count: int
    rule_count: int
    active_rule_count: int


class HealthResponse(BaseModel):
    status: str
    mqtt_connected: bool


# ── Agent ──

class AgentSnapshot(BaseModel):
    agent_id: str
    device_name: str
    device_type: str
    current_state: str
    previous_state: str | None
    entered_at: str
    timeout_seconds: int


class AgentDecisionResponse(BaseModel):
    id: int
    agent_id: str
    device_id: str
    state_from: str
    state_to: str
    trigger: str
    timestamp: str

    model_config = {"from_attributes": True}
