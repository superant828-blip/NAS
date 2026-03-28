#!/usr/bin/env python3
"""
机房动环监测系统 - Web展示界面
"""

from flask import Flask, render_template_string, jsonify
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'envmonitor',
    'password': 'EnvMonitor2024!',
    'database': 'env_monitor'
}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>机房动环监测系统</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: #0d1117; color: #e6edf3; font-family: 'Noto Sans SC', sans-serif; }
        .card { background: #161b22; border: 1px solid #30363d; }
        .stat-value { font-size: 2.5rem; font-weight: bold; }
        .temp-normal { color: #00c853; }
        .temp-warning { color: #ffab00; }
        .temp-danger { color: #ff1744; }
        .alarm-active { animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark border-bottom border-secondary">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">
                <i class="bi bi-thermometer-half"></i> 机房动环监测系统
            </span>
            <span class="text-muted">最后更新: {{ last_update }}</span>
        </div>
    </nav>
    
    <div class="container mt-4">
        <!-- 状态卡片 -->
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card p-4 text-center">
                    <div class="text-muted">温度</div>
                    <div class="stat-value {{ 'temp-danger' if temp > 30 or temp < 10 else 'temp-warning' if temp > 25 or temp < 15 else 'temp-normal' }}">
                        {{ "%.1f"|format(temp) }}°C
                    </div>
                    <div class="text-muted">阈值: 10-30°C</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card p-4 text-center">
                    <div class="text-muted">湿度</div>
                    <div class="stat-value {{ 'temp-warning' if humidity > 70 else 'temp-normal' }}">
                        {{ "%.1f"|format(humidity) }}%
                    </div>
                    <div class="text-muted">阈值: <80%</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card p-4 text-center">
                    <div class="text-muted">状态</div>
                    <div class="stat-value {{ 'text-danger alarm-active' if has_alarm else 'text-success' }}">
                        <i class="bi {{ 'bi-exclamation-triangle-fill' if has_alarm else 'bi-check-circle-fill' }}"></i>
                        {{ '告警中' if has_alarm else '正常' }}
                    </div>
                    <div class="text-muted">{{ device_count }} 台设备</div>
                </div>
            </div>
        </div>
        
        <!-- 图表区域 -->
        <div class="row">
            <div class="col-md-6">
                <div class="card p-3">
                    <h6>温度趋势 (24小时)</h6>
                    <canvas id="tempChart" height="150"></canvas>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card p-3">
                    <h6>湿度趋势 (24小时)</h6>
                    <canvas id="humidityChart" height="150"></canvas>
                </div>
            </div>
        </div>
        
        <!-- 告警记录 -->
        <div class="card mt-4 p-3">
            <h6><i class="bi bi-exclamation-triangle text-warning"></i> 最近告警记录</h6>
            <table class="table table-dark table-sm">
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>设备</th>
                        <th>类型</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
                    {% for alarm in alarms %}
                    <tr>
                        <td>{{ alarm.created_at }}</td>
                        <td>{{ alarm.device_id[:16] }}...</td>
                        <td><span class="badge bg-danger">{{ alarm.alarm_type }}</span></td>
                        <td>{{ alarm.alarm_message }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // 图表数据
        const tempData = {{ temp_history | tojson }};
        const humidityData = {{ humidity_history | tojson }};
        const labels = {{ time_labels | tojson }};
        
        // 温度图表
        new Chart(document.getElementById('tempChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '温度 (°C)',
                    data: tempData,
                    borderColor: '#ff5722',
                    backgroundColor: 'rgba(255,87,34,0.1)',
                    fill: true
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { min: 0, max: 50, grid: { color: '#30363d' } },
                    x: { grid: { color: '#30363d' } }
                }
            }
        });
        
        // 湿度图表
        new Chart(document.getElementById('humidityChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '湿度 (%)',
                    data: humidityData,
                    borderColor: '#2196f3',
                    backgroundColor: 'rgba(33,150,243,0.1)',
                    fill: true
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { min: 0, max: 100, grid: { color: '#30363d' } },
                    x: { grid: { color: '#30363d' } }
                }
            }
        });
    </script>
</body>
</html>
'''

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_latest_data():
    """获取最新数据"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 最新数据
    cursor.execute("""
        SELECT * FROM sensor_data 
        ORDER BY created_at DESC LIMIT 1
    """)
    latest = cursor.fetchone()
    
    # 设备数量
    cursor.execute("SELECT COUNT(DISTINCT device_id) as cnt FROM sensor_data")
    device_count = cursor.fetchone()['cnt']
    
    # 最近告警
    cursor.execute("""
        SELECT * FROM alarms 
        ORDER BY created_at DESC LIMIT 10
    """)
    alarms = cursor.fetchall()
    
    # 24小时历史数据
    cursor.execute("""
        SELECT temperature, humidity, created_at 
        FROM sensor_data 
        WHERE created_at > NOW() - INTERVAL 24 HOUR
        ORDER BY created_at ASC
    """)
    history = cursor.fetchall()
    
    conn.close()
    
    return latest, device_count, alarms, history

@app.route('/')
def index():
    latest, device_count, alarms, history = get_latest_data()
    
    if latest:
        temp = latest.get('temperature', 0)
        humidity = latest.get('humidity', 0)
        has_alarm = latest.get('alarm_status', 0) == 1
        last_update = latest.get('created_at', '')
    else:
        temp = humidity = 0
        has_alarm = False
        last_update = '无数据'
    
    # 历史数据
    temp_history = [h['temperature'] for h in history]
    humidity_history = [h['humidity'] for h in history]
    time_labels = [h['created_at'].strftime('%H:%M') for h in history]
    
    return render_template_string(HTML_TEMPLATE,
        temp=temp, humidity=humidity, has_alarm=has_alarm,
        device_count=device_count, last_update=last_update,
        alarms=alarms, temp_history=temp_history,
        humidity_history=humidity_history, time_labels=time_labels
    )

@app.route('/api/data')
def api_data():
    """API接口"""
    latest, device_count, alarms, history = get_latest_data()
    return jsonify({
        'temperature': latest.get('temperature') if latest else None,
        'humidity': latest.get('humidity') if latest else None,
        'alarm': latest.get('alarm_status', 0) == 1 if latest else False,
        'device_count': device_count,
        'history': [
            {'temp': h['temperature'], 'humidity': h['humidity'], 'time': h['created_at'].isoformat()}
            for h in history
        ]
    })

if __name__ == '__main__':
    print("启动Web服务: http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)