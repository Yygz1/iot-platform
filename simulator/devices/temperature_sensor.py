import logging
import random

from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)


class TemperatureSensor(BaseDevice):
    device_type = "temperature_sensor"

    def __init__(self, device_id: str, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 api_base: str = "http://127.0.0.1:8000", interval: float = 0, name: str = "",
                 anomaly_prob: float = 0.0):
        super().__init__(device_id, broker_host, broker_port, api_base, interval, name, anomaly_prob)
        self._temp = round(random.uniform(22.0, 28.0), 1)
        self._trend = random.uniform(-0.3, 0.3)
        self._cooling_active = False  # 风扇冷却是否激活

    def read_sensor(self) -> dict:
        self._trend += random.uniform(-0.2, 0.2)
        self._trend = max(-0.8, min(0.8, self._trend))

        # 冷却反馈：风扇启动后温度趋势向下偏移（冷却效果显著）
        cooling_offset = -2.0 if self._cooling_active else 0.0
        self._temp += self._trend + random.uniform(-0.1, 0.1) + cooling_offset
        self._temp = round(max(15.0, min(40.0, self._temp)), 1)
        return {"temperature": self._temp}

    def inject_anomaly(self, data: dict) -> dict:
        """温度异常：模拟温度突升或突降"""
        if "temperature" in data:
            data["temperature"] = round(data["temperature"] * random.uniform(1.8, 3.5), 1)
        return data

    def on_state_changed(self, key: str, value):
        """接收命令并响应冷却状态"""
        if key == "cooling_active":
            self._cooling_active = bool(value)
            logger.info("[%s] 冷却状态: %s", self.device_id,
                         "激活（温度将逐渐下降）" if self._cooling_active else "关闭")
        elif key == "power" and value == "off":
            self._cooling_active = False
            logger.info("[%s] 风扇关闭，冷却停止", self.device_id)

    def get_interval(self) -> float:
        return random.uniform(3.0, 8.0)
