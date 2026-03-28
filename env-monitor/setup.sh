#!/bin/bash
# 机房动环监测系统 - 服务启动脚本

echo "========================================"
echo "  机房动环监测系统 - 服务配置"
echo "========================================"

# 1. 安装依赖
echo "[1/5] 安装系统依赖..."
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients python3-pip

# 2. 安装Python依赖
echo "[2/5] 安装Python依赖..."
pip3 install paho-mqtt mysql-connector-python requests

# 3. 创建数据库
echo "[3/5] 创建数据库和用户..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS env_monitor;
CREATE USER IF NOT EXISTS 'envmonitor'@'localhost' IDENTIFIED BY 'EnvMonitor2024!';
GRANT ALL PRIVILEGES ON env_monitor.* TO 'envmonitor'@'localhost';
FLUSH PRIVILEGES;
"

# 4. 配置MQTT
echo "[4/5] 配置MQTT..."
sudo cp /etc/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf.bak
cat | sudo tee /etc/mosquitto/conf.d/env-monitor.conf > /dev/null << 'EOF'
listener 1883
allow_anonymous true
EOF

# 5. 启动服务
echo "[5/5] 启动服务..."
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager

echo ""
echo "========================================"
echo "  配置完成！"
echo "========================================"
echo ""
echo "启动MQTT接收服务:"
echo "  cd ~/env-monitor/scripts && python3 mqtt_receiver.py"
echo ""
echo "ESP32配置 - 修改以下内容后编译烧录:"
echo "  WiFi SSID: Your_WiFi_SSID"
echo "  WiFi密码: Your_WiFi_Password"  
echo "  MQTT服务器: 192.168.80.209"
echo ""
echo "Web查看数据 (可选):"
echo "  访问 http://192.168.80.209:8080"