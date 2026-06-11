"""
温度传感器示例 — ESP32 + DHT22

硬件连接:
  DHT22 VCC → 3.3V
  DHT22 GND → GND
  DHT22 DATA → GPIO4

使用前:
  1. 在平台创建设备 sensor-01（类型: temperature_sensor）
  2. 修改 BROKER 为你的平台 IP
  3. 将 iot_device.py 和此文件上传到 ESP32
"""

import time
import machine
import dht
from iot_device import IoTDevice

# ── 配置 ──
DEVICE_ID = "sensor-01"
BROKER = "192.168.1.100"  # 改为你的平台 IP
PIN = 4                    # DHT22 数据引脚

# ── 初始化 ──
sensor = dht.DHT22(machine.Pin(PIN))
device = IoTDevice(DEVICE_ID, BROKER)

# 注册命令处理（温度传感器通常不需要，但保留接口）
def on_command(cmd):
    print("收到命令:", cmd)

device.on_command(on_command)

# 连接
device.connect()

# ── 主循环 ──
while True:
    try:
        sensor.measure()
        temp = sensor.temperature()
        humi = sensor.humidity()

        # 上报遥测
        device.report({"temperature": temp, "humidity": humi})
        print(f"温度: {temp}°C, 湿度: {humi}%")

    except Exception as e:
        print("传感器读取失败:", e)

    # 处理 MQTT 消息
    device.tick()
    time.sleep(5)
