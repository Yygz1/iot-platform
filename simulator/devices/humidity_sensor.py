import random

from devices.base_device import BaseDevice


class HumiditySensor(BaseDevice):
    device_type = "humidity_sensor"

    def __init__(self, device_id: str, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 api_base: str = "http://127.0.0.1:8000", interval: float = 0, name: str = "",
                 anomaly_prob: float = 0.0):
        super().__init__(device_id, broker_host, broker_port, api_base, interval, name, anomaly_prob)
        self._humidity = round(random.uniform(40.0, 70.0), 1)
        self._trend = random.uniform(-0.5, 0.5)

    def read_sensor(self) -> dict:
        self._trend += random.uniform(-0.3, 0.3)
        self._trend = max(-1.5, min(1.5, self._trend))
        self._humidity += self._trend + random.uniform(-0.3, 0.3)
        self._humidity = round(max(20.0, min(95.0, self._humidity)), 1)
        return {"humidity": self._humidity}

    def inject_anomaly(self, data: dict) -> dict:
        """湿度异常：模拟湿度骤降"""
        if "humidity" in data:
            data["humidity"] = round(data["humidity"] * random.uniform(0.1, 0.5), 1)
        return data

    def on_state_changed(self, key: str, value):
        pass

    def get_interval(self) -> float:
        return random.uniform(5.0, 10.0)
