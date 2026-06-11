import logging
import random

from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)


class SmartLight(BaseDevice):
    device_type = "smart_light"

    def __init__(self, device_id: str, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 api_base: str = "http://127.0.0.1:8000", interval: float = 0, name: str = "",
                 anomaly_prob: float = 0.0):
        super().__init__(device_id, broker_host, broker_port, api_base, interval, name, anomaly_prob)
        self.local_state = {
            "power": "off",
            "brightness": 50,
            "color": "white",
        }

    def read_sensor(self) -> dict:
        return dict(self.local_state)

    def on_state_changed(self, key: str, value):
        logger.info("[%s] 状态变更: %s = %s", self.device_id, key, value)

    def get_interval(self) -> float:
        return random.uniform(5.0, 15.0)
