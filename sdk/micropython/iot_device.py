"""
IoT Platform 设备接入 SDK — MicroPython 版
适用于 ESP32, ESP8266, 树莓派 Pico 等 MicroPython 设备

用法:
    from iot_device import IoTDevice

    device = IoTDevice("sensor-01", "192.168.1.100")
    device.connect()

    def on_command(cmd):
        print("收到命令:", cmd)

    device.on_command(on_command)

    while True:
        device.report({"temperature": 25.3})
        device.tick()
        time.sleep(5)
"""

import json
import time
from umqtt.simple import MQTTClient


class IoTDevice:
    """IoT 平台设备接入客户端"""

    def __init__(self, device_id, broker, port=1883):
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
        self.client = MQTTClient(device_id, broker, port, keepalive=60)
        self.client.set_callback(self._on_mqtt_message)
        self._command_handler = None
        self._connected = False

        # 设置 LWT（设备离线时自动发布）
        self.client.set_last_will(
            f"devices/{device_id}/status",
            json.dumps({"status": "offline", "reason": "connection_lost"}),
            retain=True, qos=1,
        )

    def connect(self):
        """连接到 MQTT Broker"""
        try:
            self.client.connect()
            self.client.subscribe(f"devices/{self.device_id}/commands")
            self.client.publish(
                f"devices/{self.device_id}/status",
                json.dumps({"status": "online"}),
                retain=True, qos=1,
            )
            self._connected = True
            print(f"[{self.device_id}] 已连接到 {self.broker}:{self.port}")
        except Exception as e:
            print(f"[{self.device_id}] 连接失败: {e}")
            self._connected = False
            raise

    def report(self, data):
        """
        上报遥测数据

        Args:
            data: dict，如 {"temperature": 25.3}
        """
        try:
            topic = f"devices/{self.device_id}/telemetry"
            self.client.publish(topic, json.dumps(data))
        except OSError:
            self._connected = False
            raise

    def report_shadow(self, state):
        """
        上报设备影子状态

        Args:
            state: dict，如 {"power": "on", "speed": 3}
        """
        try:
            topic = f"devices/{self.device_id}/state/reported"
            self.client.publish(topic, json.dumps(state))
        except OSError:
            self._connected = False
            raise

    def on_command(self, handler):
        """
        注册命令处理函数

        Args:
            handler: 回调函数，接收一个 dict 参数
        """
        self._command_handler = handler

    def tick(self):
        """
        处理 MQTT 消息（在主循环中调用）

        失败时自动重连
        """
        try:
            self.client.check_msg()
        except OSError:
            self._connected = False
            self._reconnect()

    def is_connected(self):
        """检查连接状态"""
        return self._connected

    def disconnect(self):
        """断开连接"""
        try:
            self.client.publish(
                f"devices/{self.device_id}/status",
                json.dumps({"status": "offline", "reason": "manual"}),
                retain=True, qos=1,
            )
            self.client.disconnect()
        except Exception:
            pass
        self._connected = False

    def _on_mqtt_message(self, topic, msg):
        """内部 MQTT 消息回调"""
        try:
            topic_str = topic.decode() if isinstance(topic, bytes) else topic
            if f"devices/{self.device_id}/commands" in topic_str:
                payload = json.loads(msg)
                if self._command_handler:
                    self._command_handler(payload)
        except Exception as e:
            print(f"[{self.device_id}] 消息处理异常: {e}")

    def _reconnect(self):
        """自动重连（指数退避）"""
        delay = 1
        while not self._connected:
            try:
                print(f"[{self.device_id}] {delay}秒后重连...")
                time.sleep(delay)
                self.connect()
                print(f"[{self.device_id}] 重连成功")
            except Exception:
                delay = min(delay * 2, 30)
