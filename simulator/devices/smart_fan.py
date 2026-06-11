import asyncio
import logging
import random

from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)


class SmartFan(BaseDevice):
    device_type = "smart_fan"

    def __init__(self, device_id: str, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 api_base: str = "http://127.0.0.1:8000", interval: float = 0, name: str = "",
                 anomaly_prob: float = 0.0):
        super().__init__(device_id, broker_host, broker_port, api_base, interval, name, anomaly_prob)
        self.local_state = {
            "power": "off",
            "speed": 1,
            "mode": "normal",
        }

    def read_sensor(self) -> dict:
        return dict(self.local_state)

    def on_state_changed(self, key: str, value):
        logger.info("[%s] 风扇状态变更: %s = %s", self.device_id, key, value)
        # 收到命令后，主动把新状态上报给平台影子
        if key in ("power", "speed", "mode", "cooling_active"):
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._report_state_sync(), self._loop)

    def get_interval(self) -> float:
        return random.uniform(8.0, 15.0)

    def inject_anomaly(self, data: dict) -> dict:
        """风扇异常：转速异常跳动"""
        if "speed" in data:
            data["speed"] = random.randint(3, 5)
            data["mode"] = "abnormal"
        return data
