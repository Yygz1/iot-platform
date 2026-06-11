"""
智能风扇控制示例 — ESP32 + 继电器 + PWM 风扇

硬件连接:
  继电器 VCC → 3.3V
  继电器 GND → GND
  继电器 IN → GPIO5（电源控制）
  风扇 PWM → GPIO18（转速控制）

使用前:
  1. 在平台创建设备 fan-01（类型: smart_fan）
  2. 修改 BROKER 为你的平台 IP
"""

import time
import machine
from iot_device import IoTDevice

# ── 配置 ──
DEVICE_ID = "fan-01"
BROKER = "192.168.1.100"
RELAY_PIN = 5
PWM_PIN = 18

# ── 初始化 ──
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
pwm = machine.PWM(machine.Pin(PWM_PIN), freq=25000, duty=0)

device = IoTDevice(DEVICE_ID, BROKER)

# 当前状态
fan_power = "off"
fan_speed = 0

def set_fan(power, speed=0):
    """控制风扇"""
    global fan_power, fan_speed
    fan_power = power
    fan_speed = speed

    if power == "on":
        relay.on()
        # speed 1-5 映射到 PWM duty 20%-100%
        duty = int(speed * 20 * 10.23)  # 1023 = 100%
        pwm.duty(min(duty, 1023))
    else:
        relay.off()
        pwm.duty(0)

    # 上报新状态到平台影子
    device.report_shadow({"power": fan_power, "speed": fan_speed})
    print(f"风扇: power={fan_power}, speed={fan_speed}")

def on_command(cmd):
    """处理平台下发的命令"""
    print("收到命令:", cmd)

    power = cmd.get("power", fan_power)
    speed = cmd.get("speed", fan_speed)
    cooling = cmd.get("cooling_active")

    if power in ("on", "off"):
        set_fan(power, speed if power == "on" else 0)

device.on_command(on_command)
device.connect()

# ── 主循环 ──
while True:
    # 上报当前状态
    device.report({"power": fan_power, "speed": fan_speed, "mode": "normal"})
    device.tick()
    time.sleep(8)
