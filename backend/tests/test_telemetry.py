"""遥测历史和趋势检测单元测试"""

import time
import pytest
from app.services.telemetry_history import add, get_recent, get_values, get_stats, clear
from app.services.trend_detector import analyze, trend_slope, moving_avg, predicted_value


class TestTelemetryHistory:
    def setup_method(self):
        """每个测试前清空历史"""
        clear("test-device")

    def test_add_and_get_recent(self):
        add("test-device", {"temperature": 25.0}, time.time())
        add("test-device", {"temperature": 26.0}, time.time())
        recent = get_recent("test-device", n=10)
        assert len(recent) == 2
        assert recent[0]["data"]["temperature"] == 25.0
        assert recent[1]["data"]["temperature"] == 26.0

    def test_max_points(self):
        """测试环形缓冲区上限"""
        for i in range(250):
            add("test-device", {"temperature": float(i)}, time.time())
        recent = get_recent("test-device", n=300)
        assert len(recent) == 200  # MAX_POINTS = 200

    def test_get_values(self):
        for i in range(10):
            add("test-device", {"temperature": float(i), "humidity": float(i * 2)}, time.time())
        temps = get_values("test-device", "temperature", n=5)
        assert len(temps) == 5
        assert temps == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_get_stats(self):
        for i in range(20):
            add("test-device", {"temperature": 20.0 + i * 0.5}, time.time())
        stats = get_stats("test-device", "temperature", n=20)
        assert stats["count"] == 20
        assert 20.0 < stats["mean"] < 30.0
        assert stats["std"] > 0
        assert stats["min"] == 20.0
        assert stats["max"] > 20.0
        assert stats["slope"] > 0  # 正斜率（上升趋势）

    def test_get_stats_insufficient_data(self):
        add("test-device", {"temperature": 25.0}, time.time())
        stats = get_stats("test-device", "temperature", n=10)
        assert stats["count"] == 1
        assert stats["slope"] == 0

    def test_empty_device(self):
        recent = get_recent("nonexistent", n=10)
        assert recent == []
        values = get_values("nonexistent", "temperature", n=10)
        assert values == []


class TestTrendDetector:
    def setup_method(self):
        clear("test-device")

    def test_rising_trend(self):
        """上升趋势"""
        for i in range(20):
            add("test-device", {"temperature": 20.0 + i}, time.time())
        result = analyze("test-device", "temperature", n=20)
        assert result.direction == "rising"
        assert result.slope > 0
        assert result.predicted > 30.0

    def test_falling_trend(self):
        """下降趋势"""
        for i in range(20):
            add("test-device", {"temperature": 40.0 - i}, time.time())
        result = analyze("test-device", "temperature", n=20)
        assert result.direction == "falling"
        assert result.slope < 0
        assert result.predicted < 30.0

    def test_stable_trend(self):
        """平稳趋势"""
        for i in range(20):
            add("test-device", {"temperature": 25.0 + (i % 2) * 0.1}, time.time())
        result = analyze("test-device", "temperature", n=20)
        assert result.direction == "stable"
        assert abs(result.slope) < 0.1

    def test_anomaly_detection(self):
        """异常检测"""
        # 添加正常数据
        for i in range(20):
            add("test-device", {"temperature": 25.0 + (i % 3) * 0.5}, time.time())
        # 添加异常值
        add("test-device", {"temperature": 100.0}, time.time())
        result = analyze("test-device", "temperature", n=21, sigma=2.0)
        assert result.is_anomaly is True

    def test_no_anomaly(self):
        """正常值不触发异常"""
        for i in range(20):
            add("test-device", {"temperature": 25.0 + (i % 3) * 0.5}, time.time())
        result = analyze("test-device", "temperature", n=20, sigma=2.0)
        assert result.is_anomaly is False

    def test_insufficient_data(self):
        """数据不足时返回默认值"""
        add("test-device", {"temperature": 25.0}, time.time())
        result = analyze("test-device", "temperature", n=20)
        assert result.direction == "stable"
        assert result.slope == 0
        assert result.confidence == 0.0

    def test_helper_functions(self):
        """测试便捷函数"""
        for i in range(20):
            add("test-device", {"temperature": 20.0 + i}, time.time())

        slope = trend_slope("test-device", "temperature", n=20)
        assert slope > 0

        avg = moving_avg("test-device", "temperature", n=10)
        assert avg > 20.0  # 最近 10 个值的均值应大于 20

        pred = predicted_value("test-device", "temperature", steps=10)
        assert pred > 20.0  # 预测值应大于起始值
