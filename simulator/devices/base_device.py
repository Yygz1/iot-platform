import asyncio
import json
import logging
import random
import threading
import time
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class BaseDevice(ABC):
    device_type: str = "base"

    def __init__(self, device_id: str, broker_host: str = "127.0.0.1", broker_port: int = 1883,
                 api_base: str = "http://127.0.0.1:8000", interval: float = 0, name: str = "",
                 anomaly_prob: float = 0.0):
        self.device_id = device_id
        self.device_name = name or f"{self.device_type}-{device_id[:8]}"
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.api_base = api_base
        self._custom_interval = interval  # 0 = use per-type default
        self.anomaly_prob = anomaly_prob  # 异常数据概率 (0.0 ~ 1.0)
        self.local_state: dict = {}
        self._state_lock = threading.Lock()
        self.shadow_version = 0
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

        # MQTT Last Will Testament: 设备意外断连时，Broker 自动发布此消息
        lwt_topic = f"devices/{self.device_id}/status"
        lwt_payload = json.dumps({"status": "offline", "device_id": self.device_id, "reason": "connection_lost"})

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.will_set(lwt_topic, lwt_payload, qos=1, retain=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("[%s] MQTT 已连接", self.device_id)
            # 上线通知
            client.publish(f"devices/{self.device_id}/status",
                           json.dumps({"status": "online", "device_id": self.device_id}), qos=1, retain=True)
            client.subscribe(f"devices/{self.device_id}/state/delta")
            client.subscribe(f"devices/{self.device_id}/commands")
        else:
            logger.error("[%s] MQTT 连接失败: %s", self.device_id, reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("[%s] 收到无法解析的消息: topic=%s", self.device_id, msg.topic)
            return

        delta_topic = f"devices/{self.device_id}/state/delta"
        cmd_topic = f"devices/{self.device_id}/commands"
        if msg.topic == delta_topic:
            self._handle_delta(payload)
        elif msg.topic == cmd_topic:
            self._handle_command(payload)

    def _handle_delta(self, payload: dict):
        logger.info("[%s] 收到 Delta: %s", self.device_id, payload)
        delta_state = payload.get("state", {})
        with self._state_lock:
            for key, val in delta_state.items():
                self.local_state[key] = val
        for key, val in delta_state.items():
            self.on_state_changed(key, val)
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._report_state_sync(), self._loop)

    async def _report_state_sync(self):
        try:
            import requests as _req
            import asyncio
            def _put():
                r = _req.put(
                    f"{self.api_base}/api/devices/{self.device_id}/shadow/reported",
                    json={"state": dict(self.local_state), "version": self.shadow_version},
                    timeout=10,
                )
                return r
            resp = await asyncio.to_thread(_put)
            if resp.status_code == 200:
                data = resp.json()
                self.shadow_version = data.get("version", self.shadow_version)
                logger.debug("[%s] 状态上报成功 v%d", self.device_id, self.shadow_version)
            elif resp.status_code == 409:
                data = resp.json()
                current_ver = data.get("current_version", 0)
                logger.warning("[%s] 版本冲突 (本地v%d, 服务端v%d), 重新同步",
                               self.device_id, self.shadow_version, current_ver)
                await self._sync_shadow()
        except Exception:
            logger.exception("[%s] 状态上报失败", self.device_id)

    async def _sync_shadow(self):
        try:
            import requests as _req
            import asyncio
            def _get():
                return _req.get(f"{self.api_base}/api/devices/{self.device_id}/shadow", timeout=10)
            resp = await asyncio.to_thread(_get)
            if resp.status_code == 200:
                data = resp.json()
                self.shadow_version = data["version"]
                self.local_state.update(data["state"]["reported"])
                logger.info("[%s] 影子同步完成 v%d", self.device_id, self.shadow_version)
        except Exception:
            logger.exception("[%s] 影子同步失败", self.device_id)

    def _handle_command(self, payload: dict):
        logger.info("[%s] 收到指令: %s", self.device_id, payload)
        with self._state_lock:
            for key, val in payload.items():
                self.local_state[key] = val
        for key, val in payload.items():
            self.on_state_changed(key, val)

    @abstractmethod
    def read_sensor(self) -> dict:
        ...

    def read_sensor_with_anomaly(self) -> dict:
        """包装 read_sensor，按概率注入异常数据"""
        data = self.read_sensor()
        if self.anomaly_prob > 0 and random.random() < self.anomaly_prob:
            data = self.inject_anomaly(data)
        return data

    def inject_anomaly(self, data: dict) -> dict:
        """子类可重写以定制异常行为。默认：数值翻倍"""
        anomaly = {}
        for k, v in data.items():
            if isinstance(v, (int, float)):
                anomaly[k] = round(v * random.uniform(1.5, 3.0), 1)
            else:
                anomaly[k] = v
        logger.warning("[%s] 注入异常数据: 正常=%s → 异常=%s", self.device_id, data, anomaly)
        return anomaly

    @abstractmethod
    def on_state_changed(self, key: str, value):
        ...

    @abstractmethod
    def get_interval(self) -> float:
        ...

    def connect(self):
        self._client.connect_async(self.broker_host, self.broker_port, 60)
        self._client.loop_start()

    def publish_telemetry(self, data: dict):
        self._client.publish(f"devices/{self.device_id}/telemetry", json.dumps(data), qos=1)

    async def run(self):
        self._running = True
        self._loop = asyncio.get_running_loop()
        self.connect()
        interval = self._custom_interval if self._custom_interval > 0 else self.get_interval()
        logger.info("[%s] %s 启动, 上报间隔 %.1fs, 异常概率 %.0f%%",
                     self.device_id, self.device_name, interval, self.anomaly_prob * 100)

        # 校验设备是否已被管理员在平台预注册
        try:
            import requests as _req
            def _check():
                r = _req.get(f"{self.api_base}/api/devices/{self.device_id}", timeout=10)
                if r.status_code == 200:
                    r2 = _req.get(f"{self.api_base}/api/devices/{self.device_id}/shadow", timeout=10)
                    return r, r2
                return r, None
            resp, shadow_resp = await asyncio.to_thread(_check)
            if resp.status_code == 200:
                logger.info("[%s] 设备已在平台预注册", self.device_id)
                if shadow_resp and shadow_resp.status_code == 200:
                    data = shadow_resp.json()
                    self.shadow_version = data["version"]
            else:
                logger.error("[%s] 设备未在平台预注册! 请管理员先在平台创建设备 (名称=%s 类型=%s ID=%s)",
                             self.device_id, self.device_name, self.device_type, self.device_id)
                self._cleanup()
                return
        except Exception:
            logger.exception("[%s] 设备校验失败", self.device_id)
            self._cleanup()
            return

        while self._running:
            try:
                telemetry = self.read_sensor_with_anomaly()
                with self._state_lock:
                    self.local_state.update(telemetry)
                self.publish_telemetry(telemetry)
                logger.debug("[%s] 遥测: %s", self.device_id, telemetry)
                await self._report_state_sync()
            except Exception:
                logger.exception("[%s] 循环异常", self.device_id)

            await asyncio.sleep(interval)

    def _cleanup(self):
        """清理 MQTT 资源（注册失败或异常退出时调用）"""
        self._running = False
        self._client.publish(f"devices/{self.device_id}/status",
                             json.dumps({"status": "offline", "device_id": self.device_id}), qos=1, retain=True)
        self._client.loop_stop()
        self._client.disconnect()

    def stop(self):
        self._cleanup()
