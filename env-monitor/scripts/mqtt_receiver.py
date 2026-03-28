#!/usr/bin/env python3
"""
机房动环监测系统 - MQTT接收与存储服务
功能：订阅MQTT主题，存储数据到MySQL，推送告警通知
"""

import paho.mqtt.client as mqtt
import mysql.connector
import json
import time
import requests
from datetime import datetime

# ==================== 配置 ====================
MQTT_BROKER = "192.168.80.209"
MQTT_PORT = 1883
MQTT_TOPIC = "env/monitor"

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'envmonitor',
    'password': 'EnvMonitor2024!',
    'database': 'env_monitor'
}

# 推送配置 (可选择微信/飞书/钉钉)
PUSH_CONFIG = {
    'wechat_webhook': '',  # 企业微信 webhook
    'feishu_webhook': '',   # 飞书 webhook  
    'dingtalk_webhook': '', # 钉钉 webhook
}

# 告警阈值
TEMP_THRESHOLD_HIGH = 30.0
TEMP_THRESHOLD_LOW = 10.0
HUMIDITY_THRESHOLD_HIGH = 80

# ==================== 数据库初始化 ====================
def init_db():
    """初始化数据库和表"""
    conn = mysql.connector.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )
    cursor = conn.cursor()
    
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    cursor.execute(f"USE {DB_CONFIG['database']}")
    
    # 传感器数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(64),
            temperature FLOAT,
            humidity FLOAT,
            ip_address VARCHAR(64),
            rssi INT,
            alarm_status TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_device (device_id),
            INDEX idx_created (created_at)
        )
    """)
    
    # 告警记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(64),
            alarm_type VARCHAR(64),
            alarm_value FLOAT,
            alarm_message TEXT,
            push_status TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_device (device_id),
            INDEX idx_created (created_at)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized")

# ==================== 数据存储 ====================
def save_sensor_data(data):
    """存储传感器数据"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        alarm_status = 1 if data.get('alarm_triggered', False) else 0
        
        cursor.execute("""
            INSERT INTO sensor_data 
            (device_id, temperature, humidity, ip_address, rssi, alarm_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['device_id'],
            data['temperature'],
            data['humidity'],
            data.get('ip', ''),
            data.get('rssi', 0),
            alarm_status
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

# ==================== 告警处理 ====================
def check_and_alarm(data):
    """检查阈值并触发告警"""
    alarms = []
    
    if data['temperature'] > TEMP_THRESHOLD_HIGH:
        alarms.append({
            'type': 'temp_high',
            'value': data['temperature'],
            'message': f"温度过高: {data['temperature']:.1f}°C (阈值: {TEMP_THRESHOLD_HIGH}°C)"
        })
    
    if data['temperature'] < TEMP_THRESHOLD_LOW:
        alarms.append({
            'type': 'temp_low', 
            'value': data['temperature'],
            'message': f"温度过低: {data['temperature']:.1f}°C (阈值: {TEMP_THRESHOLD_LOW}°C)"
        })
    
    if data['humidity'] > HUMIDITY_THRESHOLD_HIGH:
        alarms.append({
            'type': 'humidity_high',
            'value': data['humidity'],
            'message': f"湿度过高: {data['humidity']:.1f}% (阈值: {HUMIDITY_THRESHOLD_HIGH}%)"
        })
    
    return alarms

def save_alarm(device_id, alarm_type, value, message):
    """保存告警记录"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alarms (device_id, alarm_type, alarm_value, alarm_message)
            VALUES (%s, %s, %s, %s)
        """, (device_id, alarm_type, value, message))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save alarm error: {e}")

def send_push_notification(message):
    """推送通知"""
    # 钉钉
    if PUSH_CONFIG['dingtalk_webhook']:
        try:
            requests.post(PUSH_CONFIG['dingtalk_webhook'], json={
                'msgtype': 'text',
                'text': {'content': f"机房告警: {message}"}
            }, timeout=5)
        except Exception as e:
            print(f"DingTalk push error: {e}")
    
    # 飞书
    if PUSH_CONFIG['feishu_webhook']:
        try:
            requests.post(PUSH_CONFIG['feishu_webhook'], json={
                'msg_type': 'text',
                'content': {'text': f"机房告警: {message}"}
            }, timeout=5)
        except Exception as e:
            print(f"Feishu push error: {e}")
    
    # 企业微信
    if PUSH_CONFIG['wechat_webhook']:
        try:
            requests.post(PUSH_CONFIG['wechat_webhook'], json={
                'msgtype': 'text',
                'text': {'content': f"机房告警: {message}"}
            }, timeout=5)
        except Exception as e:
            print(f"WeChat push error: {e}")

# ==================== MQTT回调 ====================
def on_message(client, userdata, msg):
    """接收MQTT消息"""
    try:
        payload = json.loads(msg.payload.decode())
        print(f"Received: {payload}")
        
        # 检查告警
        alarms = check_and_alarm(payload)
        if alarms:
            payload['alarm_triggered'] = True
            for alarm in alarms:
                print(f"ALARM: {alarm['message']}")
                save_alarm(payload['device_id'], alarm['type'], 
                          alarm['value'], alarm['message'])
                send_push_notification(alarm['message'])
        else:
            payload['alarm_triggered'] = False
        
        # 存储数据
        save_sensor_data(payload)
        
    except Exception as e:
        print(f"Process error: {e}")

def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        print(f"Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"MQTT connection failed: {rc}")

# ==================== 主程序 ====================
def main():
    print("=" * 50)
    print("机房动环监测系统 - MQTT接收服务")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    
    # 创建MQTT客户端
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # 连接MQTT
    print(f"Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"MQTT connection error: {e}")
        print("请确保MQTT服务已启动: sudo systemctl start mosquitto")

if __name__ == "__main__":
    main()