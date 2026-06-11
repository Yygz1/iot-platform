# 🏭 IoT 设备影子与分布式智能体平台

一个基于 **设备影子 + 分布式 Agent + 自适应阈值 + 因果推理 + 对话式交互** 的物联网监控平台。

设备不是哑终端——每个设备拥有独立的智能体（Agent），能感知历史趋势、预测未来状态、自动与其他设备协作、并用自然语言解释决策原因。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                  │
│                   http://localhost                                │
└──────────────┬──────────────────────────────────┬───────────────┘
               │ HTTP /api                        │ WebSocket /mqtt
               ▼                                  ▼
┌──────────────────────┐              ┌──────────────────────┐
│   Frontend (Nginx)   │──────────────│   Mosquitto Broker   │
│   React + Ant Design │   proxy      │   MQTT TCP + WS      │
└──────────┬───────────┘              └──────┬──────┬────────┘
           │                                │      │
           ▼                                │      │
┌──────────────────────┐                    │      │
│   Backend (FastAPI)   │◄──────────────────┘      │
│   ┌───────────────┐   │   MQTT subscribe         │
│   │ Agent Engine   │   │                          │
│   │ 状态机+因果推理 │   │                          │
│   ├───────────────┤   │                          │
│   │ Rule Engine    │   │                          │
│   │ 规则引擎       │   │                          │
│   ├───────────────┤   │                          │
│   │ Trend Detector │   │                          │
│   │ 趋势分析+预测  │   │                          │
│   ├───────────────┤   │                          │
│   │ Causal Analyzer│   │                          │
│   │ 因果推理+对话  │   │                          │
│   ├───────────────┤   │                          │
│   │ LLM Advisor    │   │                          │
│   │ Ollama 诊断    │   │                          │
│   └───────────────┘   │                          │
└───┬──────┬──────┬─────┘                          │
    │      │      │                                │
    ▼      ▼      ▼                                ▼
┌──────┐┌──────┐┌──────┐              ┌──────────────────────┐
│ PG   ││Redis ││Prom  │              │   IoT 设备模拟器      │
│数据  ││缓存  ││监控  │              │  温度/湿度/灯/风扇    │
└──────┘└──────┘└──────┘              └──────────────────────┘
```

## ✨ 核心特性

### 🔌 设备生命周期管理
- 管理员完全掌控：创建 → 激活 → 禁用/维护 → 恢复 → 退役
- 生命周期状态：`pending`（待激活）→ `active`（运行中）⇄ `suspended`（已禁用）→ `decommissioned`（已退役）
- 非 `active` 设备拒绝上报，Agent 自动联动
- 支持编辑设备信息（名称、位置、描述）
- 设备删除时自动清理 Agent 缓存

### 🔲 设备影子（Device Shadow）
- 期望状态 vs 上报状态的差异对比
- 乐观锁版本控制，防止并发冲突
- Delta 推送：状态变化实时通知设备

### 🤖 分布式智能体（Agent）
- **状态机引擎**：OFFLINE → NORMAL → WARNING → CRITICAL
- **自适应阈值**：基于历史均值 + 2σ 动态计算，告别硬编码
- **趋势感知**：移动平均、线性回归斜率、变化率、未来预测
- **异常检测**：Z-Score 统计偏离检测
- **超时升级**：WARNING 超 30 分钟自动升级为 CRITICAL
- **因果推理**：状态转换时自动生成中文解释（不只是"条件满足"）

### 💬 对话式交互
- 用户可直接向 Agent 提问（如"为什么温度高？"）
- LLM 智能回答（Ollama qwen2.5:0.5b）
- LLM 不可用时自动降级为规则化模板回答
- 意图识别：无关问题自动拒绝，引导用户提问设备相关问题
- 快捷问题按钮：为什么进入当前状态？预测趋势？建议什么操作？

### 🤝 Agent 协作
- 温度 Agent 检测异常 → 自动请求风扇 Agent 降温
- 风扇收到命令 → 开机 → 上报状态 → 回复确认
- 温度传感器感知冷却效果 → 温度逐渐下降 → 恢复正常
- 完整闭环：检测 → 决策 → 行动 → 反馈 → 恢复

### 📊 可观测性
- **Prometheus**：设备数、Agent 状态、遥测吞吐、API 延迟等指标
- **Grafana**：预置仪表盘，设备在线率、Agent 状态分布、数据趋势一目了然

### ⚙️ 规则引擎
- MQTT 通配符主题匹配
- safe 表达式求值（simpleeval），支持自适应阈值和趋势函数
- 4 种动作：日志、MQTT 发布、HTTP Webhook、设置影子期望状态
- 冷却期防重复触发

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + asyncpg |
| 前端 | React 18 + TypeScript + Ant Design + TanStack Query |
| 数据库 | PostgreSQL 16 + Redis 7 |
| MQTT | Eclipse Mosquitto 2 |
| AI | Ollama (qwen2.5:0.5b) |
| 监控 | Prometheus + Grafana |
| 部署 | Docker Compose（9 个服务） |

## 🚀 快速开始

### 前置要求
- Docker Desktop（含 WSL2）

### 一键部署

```bash
cd iot-platform
docker compose up -d
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost | 设备管理、Agent 监控、仪表盘 |
| 后端 API | http://localhost:8000 | REST API + Swagger 文档 (/docs) |
| Prometheus | http://localhost:9090 | 指标查询 |
| Grafana | http://localhost:3000 | 监控仪表盘（免登录） |

### 启动模拟器

模拟器已内置在 Docker Compose 中（4 台设备自动启动）：
- `sensor-01`：温度传感器（15% 异常概率）
- `fan-01`：智能风扇
- `light-01`：智能灯
- `sensor-02`：湿度传感器

## 📁 项目结构

```
iot-platform/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── engine.py          # Agent 状态机核心引擎
│   │   │   ├── state_machine.py   # 状态定义 + 转换规则
│   │   │   ├── policies.py        # 设备策略（自适应阈值 + 趋势条件）
│   │   │   └── llm_advisor.py     # LLM 诊断（Ollama）
│   │   ├── routers/
│   │   │   ├── agents.py          # Agent API（状态、趋势、对话）
│   │   │   ├── devices.py         # 设备 + 影子 + 生命周期 API
│   │   │   ├── rules.py           # 规则管理 API
│   │   │   └── logs.py            # 事件日志 API
│   │   ├── services/
│   │   │   ├── telemetry_cache.py     # 遥测缓存
│   │   │   ├── telemetry_history.py   # 遥测历史（环形缓冲区）
│   │   │   ├── trend_detector.py      # 趋势分析引擎
│   │   │   ├── causal_analyzer.py     # 因果推理 + 对话交互
│   │   │   ├── expression.py          # 安全表达式求值（含趋势函数）
│   │   │   ├── rule_engine.py         # 规则引擎
│   │   │   ├── agent_bus.py           # Agent 间通信总线
│   │   │   ├── device_shadow.py       # 设备影子服务
│   │   │   └── mqtt_client.py         # MQTT 客户端（线程安全）
│   │   ├── models.py              # SQLAlchemy 模型
│   │   └── main.py                # FastAPI 应用入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard/         # 仪表盘（监控状态栏 + 实时遥测）
│   │   │   ├── Devices/           # 设备管理（生命周期 + 影子 + 编辑）
│   │   │   ├── Rules/             # 规则管理
│   │   │   ├── Logs/              # 事件日志
│   │   │   └── Agents/            # 智能体（状态图 + 趋势 + 对话）
│   │   ├── hooks/
│   │   │   ├── useMqtt.ts         # MQTT WebSocket + HTTP 轮询双通道
│   │   │   └── mqttContext.tsx
│   │   └── api/
│   ├── Dockerfile
│   └── nginx.conf
├── simulator/
│   ├── devices/
│   │   ├── base_device.py         # 模拟器基类（MQTT + LWT + 影子同步）
│   │   ├── temperature_sensor.py  # 温度传感器（冷却反馈机制）
│   │   ├── humidity_sensor.py     # 湿度传感器
│   │   ├── smart_light.py         # 智能灯
│   │   └── smart_fan.py           # 智能风扇（命令响应 + 状态回报）
│   ├── main.py                    # 模拟器启动器
│   └── Dockerfile
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   └── dashboards/
│   └── dashboards/
│       └── iot-platform.json      # 预置 Grafana 仪表盘
├── mosquitto/
│   └── mosquitto.conf
├── docker-compose.yml
└── README.md
```

## 📡 API 概览

### 设备管理
```
GET    /api/devices                      # 设备列表（支持 status/type/lifecycle 过滤）
POST   /api/devices                      # 创建设备
GET    /api/devices/{id}                 # 设备详情
PUT    /api/devices/{id}                 # 更新设备信息
DELETE /api/devices/{id}                 # 删除设备
POST   /api/devices/{id}/enable          # 激活设备
POST   /api/devices/{id}/disable         # 禁用设备
PUT    /api/devices/{id}/lifecycle       # 修改生命周期状态
GET    /api/devices/{id}/shadow          # 设备影子
PUT    /api/devices/{id}/shadow/desired  # 更新期望状态
```

### 智能体
```
GET    /api/agents                       # Agent 列表
GET    /api/agents/{id}/state            # Agent 当前状态
GET    /api/agents/{id}/decisions        # 决策历史
GET    /api/agents/{id}/trend            # 趋势分析
POST   /api/agents/{id}/ask              # 智能问答
```

### 规则引擎
```
GET    /api/rules                        # 规则列表
POST   /api/rules                        # 创建规则
PUT    /api/rules/{id}                   # 更新规则
DELETE /api/rules/{id}                   # 删除规则
PUT    /api/rules/{id}/toggle            # 启停规则
```

### 认证
```
POST   /api/auth/login                   # 登录获取 Token
POST   /api/auth/register                # 注册管理员（首次）
GET    /api/auth/me                      # 当前用户信息
GET    /api/auth/check                   # 检查是否已有管理员
```

### 通知
```
GET    /api/notifications                # 通知渠道列表
POST   /api/notifications                # 添加通知渠道
POST   /api/notifications/{id}/test      # 测试发送
GET    /api/notifications/log-entries    # 通知历史
```

### 其他
```
GET    /api/telemetry                    # 实时遥测
GET    /api/logs                         # 事件日志
GET    /api/stats                        # 统计数据
GET    /metrics                          # Prometheus 指标
```

## 🧠 智能体工作流程

```
温度传感器上报 28.5°C
        │
        ▼
  Agent 引擎评估
        │
        ├─ 趋势分析：斜率 +0.31/次，持续上升
        ├─ 自适应阈值：26.8°C（均值22.1 + 2σ）
        ├─ 预测：15分钟后达 32°C
        └─ 异常检测：偏离均值 > 2σ
        │
        ▼
  状态转换：NORMAL → WARNING
        │
        ├─ 因果推理生成解释：
        │   "设备进入预警状态。温度从22.3°C上升至28.5°C，
        │    近期斜率+0.31/次。自适应阈值26.8°C。"
        ├─ 发送设备命令：fan-01 开机，转速 3
        ├─ 发送协作请求：请求风扇 Agent 降温
        └─ 记录决策日志
        │
        ▼
  风扇 Agent 响应
        │
        ├─ 收到命令 → 开机，转速 3
        ├─ 上报新状态到平台影子
        └─ 回复确认：已启动
        │
        ▼
  温度传感器感知冷却
        │
        ├─ 冷却反馈激活，温度趋势向下
        └─ 温度逐渐恢复到 22°C
        │
        ▼
  状态转换：WARNING → NORMAL
        │
        ├─ 因果推理："设备恢复正常"
        └─ 自动关闭风扇
```

## 💬 对话式交互示例

```
用户：为什么温度高？
Agent：温度当前28.5°C，已超过自适应阈值26.8°C。
       近期持续上升（斜率+0.31），当前值偏离正常范围。
       建议检查关联设备是否正常运行。

用户：预测趋势？
Agent：温度呈上升趋势，斜率0.31/次，预测值32.1°C。
       如持续当前趋势，约15分钟后达到告警阈值。

用户：今天天气怎么样？
Agent：我是设备诊断助手，只能回答与设备监控相关的问题。
       您可以问我：为什么温度高？预测趋势？建议什么操作？
```

## 🔌 物理设备接入

提供 3 种语言的设备 SDK，详见 [`sdk/`](sdk/)：

```python
# Python SDK — 10 行代码接入设备
from iot_device import IoTDevice

device = IoTDevice("sensor-01", "192.168.1.100")
device.connect()

def read_sensor():
    return {"temperature": 25.3}

device.loop(interval=5, callback=read_sensor)
```

| SDK | 目标平台 | 安装 |
|-----|---------|------|
| [MicroPython](sdk/micropython/) | ESP32, ESP8266, Pico | 复制 `iot_device.py` 到设备 |
| [Python](sdk/python/) | 树莓派, Linux, PC | `pip install paho-mqtt` |
| [Arduino](sdk/arduino/) | ESP32, ESP8266 | Arduino IDE 导入库 |

## 🔐 安全

- JWT Token 认证（24 小时有效期）
- 管理员账号密码登录
- 设备上报接口白名单（模拟器/SDK 免认证）
- JWT 密钥通过环境变量配置（生产环境必须修改）

## 🔧 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | `iot_platform` | 数据库名 |
| `POSTGRES_USER` | `iot` | 数据库用户 |
| `POSTGRES_PASSWORD` | `iot123` | 数据库密码 |
| `JWT_SECRET_KEY` | `dev-secret-key-...` | JWT 密钥（**生产环境必须修改**） |
| `BROKER_HOST` | `mosquitto` | MQTT Broker 地址 |
| `BROKER_PORT` | `1883` | MQTT Broker 端口 |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama API 地址 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 📜 许可证

MIT License
