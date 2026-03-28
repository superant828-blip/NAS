# 机房动环监测系统

## 系统架构

```
┌─────────────────┐      MQTT       ┌─────────────────┐
│   ESP32 + DHT22  │ ──────────────→│  Linux服务器     │
│   (温湿度传感器) │                 │                 │
│   (有源蜂鸣器)  │                 │  ┌───────────┐  │
└─────────────────┘                 │  │ Mosquitto │  │
                                     │  │   MQTT    │  │
                                     │  └───────────┘  │
                                     │  ┌───────────┐  │
                                     │  │  MySQL    │  │
                                     │  └───────────┘  │
                                     │  ┌───────────┐  │
                                     │  │ Python    │  │
                                     │  │ 接收脚本  │  │
                                     │  └───────────┘  │
                                     │  ┌───────────┐  │
                                     │  │ Web界面   │  │
                                     │  └───────────┘  │
                                     └─────────────────┘
                                              ↓
                                    微信/飞书/钉钉推送
```

## 硬件清单

| 硬件 | 数量 | 说明 |
|------|------|------|
| ESP32开发板 | 1 | 主控 |
| DHT22传感器 | 1 | 温湿度采集 |
| 有源蜂鸣器 | 1 | 本地报警 |
| 杜邦线 | 若干 | 连接线 |

## 引脚连接

```
ESP32 → DHT22
----------------
GPIO4 → Data

ESP32 → 蜂鸣器
----------------
GPIO5 → VCC (通过三极管驱动)
GND   → GND
```

## 快速开始

### 1. 服务器配置

```bash
# 进入项目目录
cd ~/env-monitor

# 运行配置脚本（需要sudo密码）
bash setup.sh
```

### 2. 启动服务

```bash
# 启动MQTT接收服务（后台运行）
cd ~/env-monitor/scripts
python3 mqtt_receiver.py &

# 启动Web界面（可选）
cd ~/env-monitor/server
python3 web.py
```

### 3. 配置ESP32

修改 `esp32/main.cpp` 中的WiFi和MQTT配置：

```cpp
#define WIFI_SSID "你的WiFi名称"
#define WIFI_PASSWORD "你的WiFi密码"
#define MQTT_SERVER "192.168.80.209"  // 服务器IP
```

使用PlatformIO或Arduino IDE编译烧录。

## 功能特性

- ✅ 实时监测温度、湿度
- ✅ 阈值告警（温度10-30°C，湿度<80%）
- ✅ 本地声光报警
- ✅ MQTT上报数据
- ✅ MySQL数据存储
- ✅ Web界面展示
- ✅ 历史曲线图
- ✅ 微信/飞书/钉钉推送

## API接口

| 接口 | 说明 |
|------|------|
| `GET /` | Web首页 |
| `GET /api/data` | JSON数据 |

## 文件结构

```
env-monitor/
├── esp32/
│   └── main.cpp          # ESP32固件
├── server/
│   └── web.py            # Web展示
├── scripts/
│   └── mqtt_receiver.py # MQTT接收服务
├── setup.sh              # 初始化脚本
└── README.md            # 说明文档
```

## 故障排除

### MQTT连接失败
```bash
# 检查MQTT服务状态
sudo systemctl status mosquitto

# 查看日志
sudo journalctl -u mosquitto -f
```

### 数据库连接失败
```bash
# 测试MySQL连接
mysql -u envmonitor -pEnvMonitor2024! -h localhost env_monitor
```

### 推送失败
检查webhook配置是否正确填写