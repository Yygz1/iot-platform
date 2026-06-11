"""Agent 引擎单元测试"""

import pytest
import asyncio
from app.agents.engine import Agent, register_agent, get_agent, unregister_agent, list_agents
from app.agents.state_machine import AgentState, TransitionRule, StateConfig, StateAction


def make_test_agent(transitions=None, states=None):
    """创建测试用 Agent"""
    if transitions is None:
        transitions = [
            TransitionRule(AgentState.NORMAL, AgentState.WARNING,
                          "payload.temperature > 28", confirmations=2, priority=10),
            TransitionRule(AgentState.WARNING, AgentState.CRITICAL,
                          "payload.temperature > 35", confirmations=1, priority=10),
            TransitionRule(AgentState.WARNING, AgentState.NORMAL,
                          "payload.temperature <= 28", confirmations=3, priority=5),
            TransitionRule(AgentState.CRITICAL, AgentState.NORMAL,
                          "payload.temperature <= 28", confirmations=5, priority=5),
        ]
    if states is None:
        states = [
            StateConfig(AgentState.NORMAL, on_enter=[
                StateAction("log", {"level": "info", "message": "恢复正常"})
            ]),
            StateConfig(AgentState.WARNING, timeout_seconds=1800, on_enter=[
                StateAction("log", {"level": "warning", "message": "温度预警"})
            ]),
            StateConfig(AgentState.CRITICAL, timeout_seconds=3600, on_enter=[
                StateAction("log", {"level": "error", "message": "温度告警"})
            ]),
        ]
    return Agent(
        device_id="test-device",
        device_name="测试设备",
        device_type="temperature_sensor",
        transitions=transitions,
        states=states,
    )


class TestAgentRegistration:
    def setup_method(self):
        # 清理
        unregister_agent("test-1")
        unregister_agent("test-2")

    def test_register_and_get(self):
        agent = make_test_agent()
        agent.device_id = "test-1"
        register_agent(agent)
        assert get_agent("test-1") is agent

    def test_get_nonexistent(self):
        assert get_agent("nonexistent") is None

    def test_unregister(self):
        agent = make_test_agent()
        agent.device_id = "test-2"
        register_agent(agent)
        unregister_agent("test-2")
        assert get_agent("test-2") is None

    def test_list_agents(self):
        agent = make_test_agent()
        agent.device_id = "test-1"
        register_agent(agent)
        agents = list_agents()
        assert any(a["agent_id"] == "test-1" for a in agents)


@pytest.mark.skip(reason="需要数据库隔离，与运行中的后端冲突")
class TestAgentEvaluation:
    def setup_method(self):
        unregister_agent("eval-test")

    @pytest.mark.asyncio
    async def test_offline_to_normal(self):
        """设备上线：OFFLINE → NORMAL"""
        agent = make_test_agent()
        agent.device_id = "eval-test"
        agent.current_state = AgentState.OFFLINE
        register_agent(agent)

        await agent.evaluate({"temperature": 25.0}, is_online=True)
        assert agent.current_state == AgentState.NORMAL

    @pytest.mark.asyncio
    async def test_normal_to_warning(self):
        """温度超标：NORMAL → WARNING（需要确认次数）"""
        agent = make_test_agent()
        agent.device_id = "eval-test"
        agent.current_state = AgentState.NORMAL
        register_agent(agent)

        # 第一次：不触发（confirmations=2）
        await agent.evaluate({"temperature": 30.0}, is_online=True)
        assert agent.current_state == AgentState.NORMAL

        # 第二次：触发
        await agent.evaluate({"temperature": 30.0}, is_online=True)
        assert agent.current_state == AgentState.WARNING

    @pytest.mark.asyncio
    async def test_warning_to_critical(self):
        """温度严重超标：WARNING → CRITICAL（confirmations=1）"""
        agent = make_test_agent()
        agent.device_id = "eval-test"
        agent.current_state = AgentState.WARNING
        register_agent(agent)

        await agent.evaluate({"temperature": 40.0}, is_online=True)
        assert agent.current_state == AgentState.CRITICAL

    @pytest.mark.asyncio
    async def test_recovery(self):
        """温度恢复：WARNING → NORMAL（需要 3 次确认）"""
        agent = make_test_agent()
        agent.device_id = "eval-test"
        agent.current_state = AgentState.WARNING
        register_agent(agent)

        for _ in range(3):
            await agent.evaluate({"temperature": 22.0}, is_online=True)
        assert agent.current_state == AgentState.NORMAL

    @pytest.mark.asyncio
    async def test_device_offline(self):
        """设备离线：任意状态 → OFFLINE"""
        agent = make_test_agent()
        agent.device_id = "eval-test"
        agent.current_state = AgentState.NORMAL
        register_agent(agent)

        await agent.evaluate({}, is_online=False)
        assert agent.current_state == AgentState.OFFLINE


class TestAgentSnapshot:
    def test_snapshot(self):
        agent = make_test_agent()
        agent.device_id = "snap-test"
        agent.current_state = AgentState.WARNING
        snap = agent.snapshot()
        assert snap["agent_id"] == "snap-test"
        assert snap["current_state"] == "warning"
        assert snap["device_name"] == "测试设备"
