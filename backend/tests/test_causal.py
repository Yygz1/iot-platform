"""因果分析和对话交互单元测试"""

import time
import pytest
import asyncio
from app.services.telemetry_history import add, clear
from app.services.causal_analyzer import (
    analyze_cause, build_context_for_question,
    _answer_with_template, _is_relevant_question,
    _get_main_field, _get_field_name, _get_unit,
)


class TestAnalyzeCause:
    def setup_method(self):
        clear("test-device")
        # 添加历史数据
        for i in range(20):
            add("test-device", {"temperature": 22.0 + i * 0.3}, time.time())

    def test_normal_to_warning(self):
        """NORMAL→WARNING 应生成有意义的解释"""
        telemetry = {"temperature": 29.0}
        result = analyze_cause("test-device", "temperature_sensor", "normal", "warning", telemetry)
        assert "预警" in result
        assert "温度" in result
        assert "°C" in result

    def test_warning_to_critical(self):
        """WARNING→CRITICAL 应包含严重描述"""
        telemetry = {"temperature": 38.0}
        result = analyze_cause("test-device", "temperature_sensor", "warning", "critical", telemetry)
        assert "告警" in result or "严重" in result

    def test_recovery(self):
        """WARNING→NORMAL 应描述恢复"""
        telemetry = {"temperature": 22.0}
        result = analyze_cause("test-device", "temperature_sensor", "warning", "normal", telemetry)
        assert "恢复" in result


class TestBuildContext:
    def setup_method(self):
        clear("test-device")
        for i in range(20):
            add("test-device", {"temperature": 25.0}, time.time())

    def test_context_fields(self):
        """上下文应包含所有必要字段"""
        ctx = build_context_for_question("test-device", "temperature_sensor")
        assert ctx["device_id"] == "test-device"
        assert ctx["device_type"] == "temperature_sensor"
        assert ctx["field_name"] == "温度"
        assert ctx["unit"] == "°C"
        assert ctx["current_value"] is not None
        assert "trend" in ctx
        assert "stats" in ctx

    def test_context_no_data(self):
        """无数据时上下文应正常返回"""
        ctx = build_context_for_question("empty-device", "temperature_sensor")
        assert ctx["current_value"] is None


class TestAnswerWithTemplate:
    def setup_method(self):
        clear("test-device")
        for i in range(20):
            add("test-device", {"temperature": 25.0 + i * 0.5}, time.time())

    def test_trend_question(self):
        ctx = build_context_for_question("test-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "预测趋势？")
        assert "温度" in answer
        assert "趋势" in answer or "上升" in answer or "下降" in answer

    def test_why_question(self):
        ctx = build_context_for_question("test-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "为什么温度高？")
        assert "温度" in answer

    def test_advice_question(self):
        ctx = build_context_for_question("test-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "建议什么操作？")
        assert len(answer) > 10

    def test_status_question(self):
        ctx = build_context_for_question("test-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "温度正常吗？")
        assert "温度" in answer

    def test_threshold_question(self):
        ctx = build_context_for_question("test-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "阈值是多少？")
        assert "阈值" in answer or "°C" in answer

    def test_none_value_handling(self):
        """当前值为 None 时不应崩溃"""
        clear("empty-device")
        ctx = build_context_for_question("empty-device", "temperature_sensor")
        answer = _answer_with_template(ctx, "温度多少？")
        assert "无数据" in answer or "温度" in answer


class TestHelperFunctions:
    def test_main_field(self):
        assert _get_main_field("temperature_sensor") == "temperature"
        assert _get_main_field("humidity_sensor") == "humidity"
        assert _get_main_field("smart_light") == "brightness"
        assert _get_main_field("smart_fan") == "speed"
        assert _get_main_field("unknown") == "temperature"

    def test_field_name(self):
        assert _get_field_name("temperature_sensor") == "温度"
        assert _get_field_name("humidity_sensor") == "湿度"

    def test_unit(self):
        assert _get_unit("temperature_sensor") == "°C"
        assert _get_unit("humidity_sensor") == "%"
        assert _get_unit("smart_light") == ""
