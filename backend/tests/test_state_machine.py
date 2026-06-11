"""状态机单元测试"""

import pytest
from app.agents.state_machine import AgentState, ALLOWED, TransitionRule, StateConfig, StateAction


class TestAgentState:
    def test_states_exist(self):
        assert AgentState.OFFLINE == "offline"
        assert AgentState.NORMAL == "normal"
        assert AgentState.WARNING == "warning"
        assert AgentState.CRITICAL == "critical"

    def test_allowed_transitions(self):
        # OFFLINE -> NORMAL
        assert AgentState.NORMAL in ALLOWED[AgentState.OFFLINE]
        # NORMAL -> WARNING, OFFLINE
        assert AgentState.WARNING in ALLOWED[AgentState.NORMAL]
        assert AgentState.OFFLINE in ALLOWED[AgentState.NORMAL]
        # WARNING -> CRITICAL, NORMAL, OFFLINE
        assert AgentState.CRITICAL in ALLOWED[AgentState.WARNING]
        assert AgentState.NORMAL in ALLOWED[AgentState.WARNING]
        assert AgentState.OFFLINE in ALLOWED[AgentState.WARNING]
        # CRITICAL -> NORMAL, OFFLINE
        assert AgentState.NORMAL in ALLOWED[AgentState.CRITICAL]
        assert AgentState.OFFLINE in ALLOWED[AgentState.CRITICAL]

    def test_invalid_transitions(self):
        # OFFLINE -> WARNING (not allowed)
        assert AgentState.WARNING not in ALLOWED[AgentState.OFFLINE]
        # OFFLINE -> CRITICAL (not allowed)
        assert AgentState.CRITICAL not in ALLOWED[AgentState.OFFLINE]
        # CRITICAL -> WARNING (not allowed)
        assert AgentState.WARNING not in ALLOWED[AgentState.CRITICAL]


class TestTransitionRule:
    def test_create_rule(self):
        rule = TransitionRule(
            source=AgentState.NORMAL,
            target=AgentState.WARNING,
            condition="payload.temperature > 28",
            confirmations=2,
            priority=10,
        )
        assert rule.source == AgentState.NORMAL
        assert rule.target == AgentState.WARNING
        assert rule.condition == "payload.temperature > 28"
        assert rule.confirmations == 2
        assert rule.priority == 10

    def test_rule_defaults(self):
        rule = TransitionRule(
            source=AgentState.NORMAL,
            target=AgentState.WARNING,
        )
        assert rule.condition == ""
        assert rule.confirmations == 1
        assert rule.priority == 0


class TestStateConfig:
    def test_create_config(self):
        action = StateAction("log", {"level": "info", "message": "test"})
        config = StateConfig(
            state=AgentState.WARNING,
            timeout_seconds=1800,
            on_enter=[action],
        )
        assert config.state == AgentState.WARNING
        assert config.timeout_seconds == 1800
        assert len(config.on_enter) == 1
        assert config.on_enter[0].action_type == "log"

    def test_config_defaults(self):
        config = StateConfig(state=AgentState.NORMAL)
        assert config.timeout_seconds == 0
        assert config.on_enter == []
        assert config.on_exit == []
