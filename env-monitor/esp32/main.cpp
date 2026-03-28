/**
 * 机房动环监测系统 - ESP32 固件
 * 功能：采集温湿度数据，监测异常并报警，支持MQTT上报
 * 硬件：ESP32 + DHT22 + 有源蜂鸣器
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// ==================== 配置 ====================
#define WIFI_SSID "Your_WiFi_SSID"
#define WIFI_PASSWORD "Your_WiFi_Password"

#define MQTT_SERVER "192.168.80.209"  // 服务器IP
#define MQTT_PORT 1883
#define MQTT_TOPIC "env/monitor"

#define DHT_PIN 4
#define DHT_TYPE DHT22
#define BUZZER_PIN 5

#define TEMP_THRESHOLD_HIGH 30.0    // 温度上限
#define TEMP_THRESHOLD_LOW 10.0     // 温度下限
#define HUMIDITY_THRESHOLD_HIGH 80 // 湿度上限

// ==================== 全局变量 ====================
DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient espClient;
PubSubClient client(espClient);

bool alarmTriggered = false;
unsigned long lastPublish = 0;
const unsigned long PUBLISH_INTERVAL = 60000; // 1分钟上报一次

// ==================== 函数声明 ====================
void setupWiFi();
void reconnectMQTT();
void publishData(float temp, float humidity);
void checkThreshold(float temp, float humidity);
void alarmOn();
void alarmOff();

// ==================== WiFi连接 ====================
void setupWiFi() {
  delay(10);
  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println("IP: " + WiFi.localIP().toString());
}

// ==================== MQTT连接 ====================
void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    String clientId = "ESP32-" + String(WiFi.macAddress());
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(5000);
    }
  }
}

// ==================== 发布数据 ====================
void publishData(float temp, float humidity) {
  if (!client.connected()) return;
  
  String payload = "{";
  payload += "\"device_id\":\"" + WiFi.macAddress() + "\",";
  payload += "\"temperature\":" + String(temp, 1) + ",";
  payload += "\"humidity\":" + String(humidity, 1) + ",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"rssi\":" + String(WiFi.RSSI());
  payload += "}";
  
  client.publish(MQTT_TOPIC, payload.c_str());
  Serial.println("Published: " + payload);
}

// ==================== 阈值检查 ====================
void checkThreshold(float temp, float humidity) {
  bool shouldAlarm = false;
  
  if (temp > TEMP_THRESHOLD_HIGH || temp < TEMP_THRESHOLD_LOW) {
    Serial.println("ALARM: Temperature abnormal!");
    shouldAlarm = true;
  }
  
  if (humidity > HUMIDITY_THRESHOLD_HIGH) {
    Serial.println("ALARM: Humidity too high!");
    shouldAlarm = true;
  }
  
  if (shouldAlarm && !alarmTriggered) {
    alarmOn();
  } else if (!shouldAlarm && alarmTriggered) {
    alarmOff();
  }
}

// ==================== 报警控制 ====================
void alarmOn() {
  digitalWrite(BUZZER_PIN, HIGH);
  alarmTriggered = true;
  Serial.println(">>> ALARM ON <<<");
}

void alarmOff() {
  digitalWrite(BUZZER_PIN, LOW);
  alarmTriggered = false;
  Serial.println(">>> ALARM OFF <<<");
}

// ==================== 设置 ====================
void setup() {
  Serial.begin(115200);
  
  // 初始化引脚
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  // 初始化DHT
  dht.begin();
  
  // 连接WiFi
  setupWiFi();
  
  // 设置MQTT
  client.setServer(MQTT_SERVER, MQTT_PORT);
}

// ==================== 主循环 ====================
void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();
  
  unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL) {
    lastPublish = now;
    
    // 读取传感器数据
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    
    if (isnan(temperature) || isnan(humidity)) {
      Serial.println("Failed to read from DHT sensor!");
      return;
    }
    
    Serial.printf("Temp: %.1f°C, Humidity: %.1f%%\n", temperature, humidity);
    
    // 上报数据
    publishData(temperature, humidity);
    
    // 检查阈值
    checkThreshold(temperature, humidity);
  }
}