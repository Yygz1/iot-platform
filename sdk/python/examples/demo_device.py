"""
本地演示设备 — 无需硬件，在电脑上模拟一台物理设备连到平台

运行方式:
  cd sdk/python
  pip install -r requirements.txt
  python examples/demo_device.py

效果:
  在前端 http://localhost/devices 看到 demo-device-01 在线
  实时遥测显示模拟的温度和湿度数据
"""

import time
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from iot_device import IoTDevice

# ── 配置 ──
DEVICE_ID = "sensor-01"  # 使用平台已有的设备
BROKER = "127.0.0.1"

# ── 初始化 ──
device = IoTDevice(DEVICE_ID, BROKER)
temp = 22.0

def on_command(cmd):
    print(f"[收到命令] {cmd}")

def read_sensor() -> dict:
    """模拟传感器读数"""
    global temp
    temp += random.uniform(-0.5, 0.5)
    temp = max(15, min(35, temp))
    humidity = random.uniform(40, 70)
    return {
        "temperature": round(temp, 1),
        "humidity": round(humidity, 1),
    }

# 连接
device.on_command(on_command)
print(f"正在连接 {BROKER}...")
device.connect()
print(f"设备 {DEVICE_ID} 已上线，每 5 秒上报一次数据")
print("按 Ctrl+C 停止\n")

# 主循环
try:
    device.loop(interval=5, callback=read_sensor)
except KeyboardInterrupt:
    print("\n停止...")
    device.stop()
    print("设备已离线")
