"""
IoT Platform 设备接入 SDK — Python 版
适用于树莓派, Linux 设备, PC 等 Python 3.8+ 环境

用法:
    from iot_device import IoTDevice

    device = IoTDevice("sensor-01", "192.168.1.100")
    device.connect()

    def on_command(cmd):
        print("收到命令:", cmd)

    device.on_command(on_command)
    device.loop(interval=5, callback=lambda: {"temperature": read_sensor()})
"""

import json
import time
import threading
import logging
from typing import Callable, Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class IoTDevice:
    """IoT 平台设备接入客户端"""

    def __init__(self, device_id: str, broker: str, port: int = 1883):
        """
        初始化设备客户端

        Args:
            device_id: 设备 ID（需在平台预注册）
            broker: MQTT Broker 地址（平台 IP）
            port: MQTT Broker 端口（默认 1883）
        """
        self.device_id = device_id
        self.broker = broker
        self.port = port

        self.client = mqtt.Client(
            client_id=device_id,
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # 设置 LWT
        self.client.will_set(
            f"devices/{device_id}/status",
            json.dumps({"status": "offline", "reason": "connection_lost"}),
            qos=1, retain=True,
        )

        self._command_handler: Callable[[dict], None] | None = None
        self._connected = False
        self._stop = False

    def connect(self):
        """连接到 MQTT Broker"""
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            # 等待连接建立
            for _ in range(50):
                if self._connected:
                    return
                time.sleep(0.1)
            raise ConnectionError("连接超时")
        except Exception as e:
            logger.error("[%s] 连接失败: %s", self.device_id, e)
            raise

    def report(self, data: dict):
        """
        上报遥测数据

        Args:
            data: dict，如 {"temperature": 25.3}
        """
        topic = f"devices/{self.device_id}/telemetry"
        self.client.publish(topic, json.dumps(data), qos=0)

    def report_shadow(self, state: dict):
        """
        上报设备影子状态

        Args:
            state: dict，如 {"power": "on", "speed": 3}
        """
        topic = f"devices/{self.device_id}/state/reported"
        self.client.publish(topic, json.dumps(state), qos=1)

    def on_command(self, handler: Callable[[dict], None]):
        """
        注册命令处理函数

        Args:
            handler: 回调函数，接收一个 dict 参数
        """
        self._command_handler = handler

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    def loop(self, interval: float = 5.0, callback: Callable[[], dict] | None = None):
        """
        主循环：自动上报 + 处理命令

        Args:
            interval: 上报间隔（秒）
            callback: 遥测数据回调函数，返回 dict
        """
        self._stop = False
        logger.info("[%s] 开始主循环，间隔 %ds", self.device_id, interval)

        while not self._stop:
            try:
                if callback:
                    data = callback()
                    if data:
                        self.report(data)
            except Exception as e:
                logger.error("[%s] 上报异常: %s", self.device_id, e)

            time.sleep(interval)

    def stop(self):
        """停止主循环并断开连接"""
        self._stop = True
        try:
            self.client.publish(
                f"devices/{self.device_id}/status",
                json.dumps({"status": "offline", "reason": "manual"}),
                qos=1, retain=True,
            )
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            self._connected = True
            client.subscribe(f"devices/{self.device_id}/commands", qos=1)
            client.publish(
                f"devices/{self.device_id}/status",
                json.dumps({"status": "online"}),
                qos=1, retain=True,
            )
            logger.info("[%s] 已连接到 %s:%d", self.device_id, self.broker, self.port)
        else:
            logger.error("[%s] 连接失败, 返回码: %d", self.device_id, rc)

    def _on_message(self, client, userdata, msg):
        """消息回调"""
        try:
            topic = msg.topic
            if f"devices/{self.device_id}/commands" in topic:
                payload = json.loads(msg.payload.decode())
                if self._command_handler:
                    self._command_handler(payload)
        except Exception as e:
            logger.error("[%s] 消息处理异常: %s", self.device_id, e)

    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        self._connected = False
        if rc != 0:
            logger.warning("[%s] 意外断开, 返回码: %d, 自动重连中...", self.device_id, rc)
