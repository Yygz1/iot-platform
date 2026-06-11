# IoT Platform 设备接入 SDK

将物理设备连接到 IoT 平台的客户端库。

## 支持平台

| SDK | 语言 | 目标硬件 | 安装 |
|-----|------|---------|------|
| [MicroPython](micropython/) | MicroPython | ESP32, ESP8266, Pico | 复制 `iot_device.py` 到设备 |
| [Python](python/) | Python 3.8+ | 树莓派, Linux, PC | `pip install paho-mqtt` |
| [Arduino](arduino/) | C++ | ESP32, ESP8266 | Arduino IDE 导入库 |

## 快速开始

### 1. 在平台创建设备

打开 http://localhost/devices → 添加设备 → 记下设备 ID 和类型

### 2. 编写设备代码

**MicroPython（ESP32）：**
```python
from iot_device import IoTDevice
import time

device = IoTDevice("sensor-01", "192.168.1.100")
device.connect()

while True:
    device.report({"temperature": 25.3})
    device.tick()
    time.sleep(5)
```

**Python（树莓派）：**
```python
from iot_device import IoTDevice

device = IoTDevice("sensor-01", "192.168.1.100")
device.connect()

def read_sensor():
    return {"temperature": 25.3}

device.loop(interval=5, callback=read_sensor)
```

**Arduino（ESP32）：**
```cpp
#include <IoTDevice.h>

IoTDevice device("sensor-01", "192.168.1.100");

void setup() {
    device.connect();
}

void loop() {
    device.report("{\"temperature\": 25.3}");
    device.tick();
    delay(5000);
}
```

## API 参考

### `IoTDevice(device_id, broker, port=1883)`

创建设备客户端实例。

### `device.connect()`

连接到 MQTT Broker。自动设置 LWT（离线遗言）。

### `device.report(data)`

上报遥测数据。`data` 为 dict（Python）或 JSON 字符串（Arduino）。

```python
device.report({"temperature": 25.3, "humidity": 60})
```

### `device.report_shadow(state)`

上报设备影子状态（用于控制类设备）。

```python
device.report_shadow({"power": "on", "speed": 3})
```

### `device.on_command(handler)`

注册命令处理函数。当平台下发命令时调用。

```python
def on_command(cmd):
    if cmd.get("power") == "on":
        turn_on()

device.on_command(on_command)
```

### `device.loop(interval, callback)`

主循环（仅 Python SDK）。自动上报 + 处理命令。

```python
device.loop(interval=5, callback=read_sensor)
```

### `device.tick()`

处理 MQTT 消息（MicroPython/Arduino SDK）。在主循环中调用。

### `device.is_connected()`

检查连接状态。

### `device.disconnect()`

断开连接并发布离线状态。

## MQTT 协议

设备使用的 MQTT 主题：

| 主题 | 方向 | 说明 |
|------|------|------|
| `devices/{id}/telemetry` | 设备→平台 | 遥测数据上报 |
| `devices/{id}/commands` | 平台→设备 | 控制命令下发 |
| `devices/{id}/status` | 设备→平台 | 在线/离线状态 |
| `devices/{id}/state/reported` | 设备→平台 | 影子上报状态 |

### 遥测数据格式

```json
{"temperature": 25.3, "humidity": 60.0}
```

### 命令格式

```json
{"power": "on", "speed": 3, "cooling_active": true}
```

## 网络要求

- 设备需与平台在同一网络，或平台 MQTT 端口（1883）对外开放
- 设备需能解析平台主机名或使用 IP 地址
- 支持 WiFi（推荐）或有线网络

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 连接失败 | Broker 地址错误或网络不通 | 检查 IP 和端口，ping 测试 |
| 设备未在平台注册 | 未在平台创建设备 | 先在前端创建设备 |
| 数据不上报 | MQTT 连接断开 | 检查网络，SDK 会自动重连 |
| 命令不生效 | 未注册 on_command | 确保调用了 `device.on_command()` |
