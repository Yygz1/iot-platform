"""物联网模拟设备启动器

用法:
    # 基础用法
    python main.py --count 3 --type temperature
    python main.py --count 2 --type humidity --broker 127.0.0.1
    python main.py --count 1 --type smart_light --name "客厅灯"
    python main.py --count 2 --type all

    # 指定设备ID和上报间隔
    python main.py --type temperature --id sensor-001 --name "机房-温度-01" --interval 5

    # 批量指定ID
    python main.py --count 2 --type smart_fan --id fan-01,fan-02

    # 异常数据模拟 (30%概率产生异常值)
    python main.py --count 2 --type temperature --anomaly 0.3
"""

import argparse
import asyncio
import logging
import uuid
import signal

from devices.temperature_sensor import TemperatureSensor
from devices.humidity_sensor import HumiditySensor
from devices.smart_light import SmartLight
from devices.smart_fan import SmartFan

logger = logging.getLogger("simulator")

DEVICE_CLASSES = {
    "temperature": TemperatureSensor,
    "humidity": HumiditySensor,
    "smart_light": SmartLight,
    "smart_fan": SmartFan,
}


def parse_args():
    p = argparse.ArgumentParser(
        description="IoT 模拟设备启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --count 3 --type temperature
  python main.py --count 2 --type all --anomaly 0.3
  python main.py --type temperature --id sensor-001 --name "机房传感器" --interval 5
        """,
    )
    p.add_argument("--count", type=int, default=1, help="设备数量（--id 指定多个时自动覆盖）")
    p.add_argument("--type", type=str, default="temperature",
                   choices=["temperature", "humidity", "smart_light", "smart_fan", "all"],
                   help="设备类型")
    p.add_argument("--id", type=str, default="", help="设备ID，多个用逗号分隔。不传则自动生成UUID")
    p.add_argument("--name", type=str, default="", help="设备名称，多个用逗号分隔。不传则自动生成")
    p.add_argument("--interval", type=float, default=0,
                   help="上报间隔(秒)，0=使用各类型的默认值")
    p.add_argument("--anomaly", type=float, default=0.0,
                   help="异常数据概率 (0.0~1.0)，例如 0.3=30%% 概率产生异常值")
    p.add_argument("--broker", type=str, default="127.0.0.1", help="MQTT Broker 地址")
    p.add_argument("--port", type=int, default=1883, help="MQTT Broker 端口")
    p.add_argument("--api", type=str, default="http://127.0.0.1:8000", help="后端 API 地址")
    return p.parse_args()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = parse_args()
    types_to_run = list(DEVICE_CLASSES.keys()) if args.type == "all" else [args.type]

    # 解析设备ID列表
    device_ids = [s.strip() for s in args.id.split(",") if s.strip()] if args.id else []
    device_names = [s.strip() for s in args.name.split(",") if s.strip()] if args.name else []

    tasks = []
    for device_type in types_to_run:
        cls = DEVICE_CLASSES[device_type]
        count = max(1, args.count // len(types_to_run)) if args.type == "all" else args.count

        for i in range(count):
            # ID 优先级：命令行指定 > 自动生成
            device_id = device_ids[i] if i < len(device_ids) else uuid.uuid4().hex[:16]
            # 名称优先级：命令行指定 > 自动生成
            device_name = device_names[i] if i < len(device_names) else ""

            device = cls(
                device_id=device_id,
                broker_host=args.broker,
                broker_port=args.port,
                api_base=args.api,
                interval=args.interval,
                name=device_name,
                anomaly_prob=args.anomaly,
            )
            tasks.append(asyncio.create_task(device.run()))

    logger.info("已启动 %d 个模拟设备", len(tasks))

    running = True

    def _stop(signum, frame):
        nonlocal running
        logger.info("正在停止所有设备...")
        running = False
        for t in tasks:
            t.cancel()

    try:
        signal.signal(signal.SIGINT, _stop)
    except (ValueError, OSError):
        pass  # Windows 不支持某些信号
    try:
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, OSError):
        pass

    try:
        while running:
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("所有设备已停止")


if __name__ == "__main__":
    asyncio.run(main())
