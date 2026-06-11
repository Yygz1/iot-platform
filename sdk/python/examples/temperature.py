"""
温度传感器示例 — 树莓派 + DHT22

硬件连接:
  DHT22 VCC → 3.3V (Pin 1)
  DHT22 GND → GND (Pin 6)
  DHT22 DATA → GPIO4 (Pin 7)
  10KΩ 上拉电阻: VCC → DATA

安装依赖:
  pip install paho-mqtt adafruit-circuitpython-dht

使用前:
  1. 在平台创建设备 sensor-01（类型: temperature_sensor）
  2. 修改 BROKER 为你的平台 IP
"""

import time
import board
import adafruit_dht
from iot_device import IoTDevice

# ── 配置 ──
DEVICE_ID = "sensor-01"
BROKER = "192.168.1.100"  # 改为你的平台 IP

# ── 初始化传感器 ──
dht_sensor = adafruit_dht.DHT22(board.D4)

# ── 初始化设备 ──
device = IoTDevice(DEVICE_ID, BROKER)


def read_sensor() -> dict:
    """读取传感器数据"""
    try:
        temp = dht_sensor.temperature
        humi = dht_sensor.humidity
        return {"temperature": round(temp, 1), "humidity": round(humi, 1)}
    except Exception as e:
        print(f"读取失败: {e}")
        return {}


def on_command(cmd: dict):
    """处理命令（温度传感器通常不需要，但保留接口）"""
    print(f"收到命令: {cmd}")


# 连接
device.on_command(on_command)
device.connect()

# 主循环：每 5 秒上报一次
print(f"设备 {DEVICE_ID} 已启动，每 5 秒上报一次")
device.loop(interval=5, callback=read_sensor)
