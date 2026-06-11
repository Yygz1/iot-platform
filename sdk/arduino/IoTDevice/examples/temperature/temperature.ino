/**
 * 温度传感器示例 — ESP32 + DHT22
 *
 * 硬件连接:
 *   DHT22 VCC → 3.3V
 *   DHT22 GND → GND
 *   DHT22 DATA → GPIO4
 *
 * Arduino 库依赖:
 *   - PubSubClient
 *   - ArduinoJson
 *   - DHT sensor library
 *
 * 使用前:
 *   1. 在平台创建设备 sensor-01（类型: temperature_sensor）
 *   2. 修改 WIFI_SSID, WIFI_PASS, BROKER
 */

#include <WiFi.h>
#include <DHT.h>
#include <IoTDevice.h>

// ── 配置 ──
#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASS "your-wifi-password"
#define BROKER    "192.168.1.100"
#define DEVICE_ID "sensor-01"
#define DHT_PIN   4

// ── 初始化 ──
DHT dht(DHT_PIN, DHT22);
IoTDevice device(DEVICE_ID, BROKER);

void onCommand(JsonDocument& cmd) {
    Serial.print("收到命令: ");
    serializeJson(cmd, Serial);
    Serial.println();
}

void setup() {
    Serial.begin(115200);
    dht.begin();

    // 连接 WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\nWiFi 已连接: %s\n", WiFi.localIP().toString().c_str());

    // 连接平台
    device.onCommand(onCommand);
    device.connect();
}

void loop() {
    device.tick();

    // 读取传感器
    float temp = dht.readTemperature();
    float humi = dht.readHumidity();

    if (!isnan(temp) && !isnan(humi)) {
        // 构建 JSON 并上报
        StaticJsonDocument<128> doc;
        doc["temperature"] = round(temp * 10) / 10.0;
        doc["humidity"] = round(humi * 10) / 10.0;
        device.report(doc);

        Serial.printf("温度: %.1f°C, 湿度: %.1f%%\n", temp, humi);
    } else {
        Serial.println("传感器读取失败");
    }

    delay(5000);
}
