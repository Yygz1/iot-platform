import asyncio
import json
import logging
from collections.abc import Callable, Awaitable

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, str], Awaitable[None]]


class MqttClient:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handlers: list[MessageHandler] = []
        self._pending_subs: list[tuple[str, int]] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT 已连接至 %s:%d", settings.broker_host, settings.broker_port)
            for topic, qos in self._pending_subs:
                self.client.subscribe(topic, qos)
        else:
            logger.error("MQTT 连接失败, 返回码: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = ""
        # 线程安全：用 call_soon_threadsafe 将数据投递到事件循环线程
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, (msg.topic, payload)
            )

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        logger.warning("MQTT 已断开, 返回码: %s", reason_code)

    async def _process_queue(self):
        while True:
            topic, payload = await self._queue.get()
            for handler in self._handlers:
                try:
                    await handler(topic, payload)
                except Exception:
                    logger.exception("消息处理器异常, topic=%s", topic)

    def add_handler(self, handler: MessageHandler):
        self._handlers.append(handler)

    def connect(self):
        self._loop = asyncio.get_running_loop()
        self.client.connect_async(settings.broker_host, settings.broker_port, 60)
        self.client.loop_start()
        self._task = asyncio.create_task(self._process_queue())

    def subscribe(self, topic: str, qos: int = 1):
        self._pending_subs.append((topic, qos))
        if self._connected:
            self.client.subscribe(topic, qos)
        logger.info("MQTT 订阅: %s", topic)

    def publish(self, topic: str, payload: dict, qos: int = 1, retain: bool = False):
        try:
            data = json.dumps(payload)
        except (TypeError, ValueError) as e:
            logger.error("MQTT 发布失败: payload 不可序列化, topic=%s, error=%s", topic, e)
            return
        self.client.publish(topic, data, qos, retain)

    async def disconnect(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False


mqtt_client = MqttClient()
