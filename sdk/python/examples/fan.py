"""
智能风扇控制示例 — 树莓派 + 继电器 + PWM 风扇

硬件连接:
  继电器 VCC → 5V (Pin 2)
  继电器 GND → GND (Pin 6)
  继电器 IN → GPIO17 (Pin 11)
  风扇 PWM → GPIO18 (Pin 12)

安装依赖:
  pip install paho-mqtt RPi.GPIO

使用前:
  1. 在平台创建设备 fan-01（类型: smart_fan）
  2. 修改 BROKER 为你的平台 IP
"""

import time
import RPi.GPIO as GPIO
from iot_device import IoTDevice

# ── 配置 ──
DEVICE_ID = "fan-01"
BROKER = "192.168.1.100"
RELAY_PIN = 17
PWM_PIN = 18

# ── 初始化 GPIO ──
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)
pwm = GPIO.PWM(PWM_PIN, 25000)  # 25kHz PWM
pwm.start(0)

# ── 设备状态 ──
fan_power = "off"
fan_speed = 0

# ── 初始化设备 ──
device = IoTDevice(DEVICE_ID, BROKER)


def set_fan(power: str, speed: int = 0):
    """控制风扇"""
    global fan_power, fan_speed
    fan_power = power
    fan_speed = speed

    if power == "on":
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        duty = speed * 20  # speed 1-5 → duty 20%-100%
        pwm.ChangeDutyCycle(duty)
    else:
        GPIO.output(RELAY_PIN, GPIO.LOW)
        pwm.ChangeDutyCycle(0)

    # 上报新状态到平台影子
    device.report_shadow({"power": fan_power, "speed": fan_speed})
    print(f"风扇: power={fan_power}, speed={fan_speed}")


def on_command(cmd: dict):
    """处理平台下发的命令"""
    print(f"收到命令: {cmd}")
    power = cmd.get("power", fan_power)
    speed = cmd.get("speed", fan_speed)
    if power in ("on", "off"):
        set_fan(power, speed if power == "on" else 0)


def get_state() -> dict:
    """获取当前状态用于上报"""
    return {"power": fan_power, "speed": fan_speed, "mode": "normal"}


# 连接
device.on_command(on_command)
device.connect()

# 主循环
print(f"设备 {DEVICE_ID} 已启动")
try:
    device.loop(interval=8, callback=get_state)
except KeyboardInterrupt:
    print("停止...")
finally:
    device.stop()
    GPIO.cleanup()
