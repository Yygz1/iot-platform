"""表达式求值单元测试"""

import pytest
from app.services.expression import evaluate_condition
from app.services.causal_analyzer import _is_relevant_question


class TestEvaluateCondition:
    def test_simple_comparison(self):
        assert evaluate_condition("payload.temperature > 28", {"temperature": 30}) is True
        assert evaluate_condition("payload.temperature > 28", {"temperature": 25}) is False

    def test_compound_condition(self):
        payload = {"temperature": 30, "humidity": 60}
        assert evaluate_condition("payload.temperature > 28 and payload.humidity > 50", payload) is True
        assert evaluate_condition("payload.temperature > 28 and payload.humidity > 70", payload) is False

    def test_or_condition(self):
        payload = {"temperature": 30}
        assert evaluate_condition("payload.temperature > 35 or payload.temperature < 10", payload) is False
        assert evaluate_condition("payload.temperature > 25 or payload.temperature < 10", payload) is True

    def test_nested_payload(self):
        payload = {"data": {"value": 42}}
        assert evaluate_condition("payload.data.value > 40", payload) is True

    def test_string_comparison(self):
        payload = {"status": "online"}
        assert evaluate_condition("payload.status == 'online'", payload) is True
        assert evaluate_condition("payload.status == 'offline'", payload) is False

    def test_invalid_expression(self):
        # Invalid expressions should return False, not raise
        assert evaluate_condition("invalid!!!", {"x": 1}) is False
        assert evaluate_condition("", {"x": 1}) is False

    def test_missing_field(self):
        # Accessing a field that doesn't exist should return False
        assert evaluate_condition("payload.temperature > 28", {"humidity": 60}) is False

    def test_with_device_functions(self):
        # Trend functions should be available when device_id is provided
        # This requires telemetry history to be populated, so we test the basic wiring
        result = evaluate_condition("payload.temperature > 28", {"temperature": 30}, device_id="test-device")
        assert result is True

    def test_builtin_functions(self):
        assert evaluate_condition("abs(payload.x) > 5", {"x": -10}) is True
        assert evaluate_condition("round(payload.x) == 3", {"x": 2.7}) is True
        assert evaluate_condition("min(payload.x, payload.y) > 5", {"x": 10, "y": 3}) is False
        assert evaluate_condition("max(payload.x, payload.y) > 5", {"x": 10, "y": 3}) is True


class TestIsRelevantQuestion:
    def test_device_related(self):
        assert _is_relevant_question("温度多少？") is True
        assert _is_relevant_question("设备状态怎么样？") is True
        assert _is_relevant_question("为什么温度高？") is True
        assert _is_relevant_question("预测趋势？") is True
        assert _is_relevant_question("建议什么操作？") is True

    def test_irrelevant(self):
        assert _is_relevant_question("asdfgh") is False
        assert _is_relevant_question("12345") is False
        assert _is_relevant_question("今天天气怎么样？") is False
        assert _is_relevant_question("你好") is False
        assert _is_relevant_question("哈哈") is False

    def test_english_relevant(self):
        assert _is_relevant_question("what is the temperature?") is True
        assert _is_relevant_question("why is the device offline?") is True
        assert _is_relevant_question("predict the trend") is True

    def test_english_irrelevant(self):
        assert _is_relevant_question("hello") is False
        assert _is_relevant_question("abc") is False
