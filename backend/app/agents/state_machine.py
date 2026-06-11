from enum import Enum
from dataclasses import dataclass, field


class AgentState(str, Enum):
    OFFLINE = "offline"
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


ALLOWED: dict[AgentState, set[AgentState]] = {
    AgentState.OFFLINE:  {AgentState.NORMAL},
    AgentState.NORMAL:   {AgentState.OFFLINE, AgentState.WARNING},
    AgentState.WARNING:  {AgentState.OFFLINE, AgentState.NORMAL, AgentState.CRITICAL},
    AgentState.CRITICAL: {AgentState.OFFLINE, AgentState.NORMAL},
}


@dataclass
class TransitionRule:
    source: AgentState
    target: AgentState
    condition: str = ""
    confirmations: int = 1
    priority: int = 0


@dataclass
class StateAction:
    action_type: str
    config: dict = field(default_factory=dict)


@dataclass
class StateConfig:
    state: AgentState
    on_enter: list[StateAction] = field(default_factory=list)
    on_exit: list[StateAction] = field(default_factory=list)
    timeout_seconds: int = 0

CONFIRMATION_LIMIT = 10
