/**
 * IoT Platform 设备接入 SDK — Arduino 版
 * 适用于 ESP32, ESP8266 等 Arduino 兼容开发板
 *
 * 用法:
 *   #include <IoTDevice.h>
 *
 *   IoTDevice device("sensor-01", "192.168.1.100");
 *
 *   void onCommand(JsonDocument& cmd) {
 *     Serial.println("收到命令");
 *   }
 *
 *   void setup() {
 *     device.onCommand(onCommand);
 *     device.connect();
 *   }
 *
 *   void loop() {
 *     device.report("{\"temperature\": 25.3}");
 *     device.tick();
 *     delay(5000);
 *   }
 */

#ifndef IOT_DEVICE_H
#define IOT_DEVICE_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

typedef void (*CommandHandler)(JsonDocument& cmd);

class IoTDevice {
public:
    IoTDevice(const char* deviceId, const char* broker, int port = 1883);

    bool connect();
    void report(const char* jsonPayload);
    void report(const String& jsonPayload);
    void report(JsonDocument& doc);
    void reportShadow(const char* jsonPayload);
    void onCommand(CommandHandler handler);
    void tick();
    bool isConnected();
    void disconnect();

private:
    const char* _deviceId;
    const char* _broker;
    int _port;
    WiFiClient _wifiClient;
    PubSubClient _mqttClient;
    CommandHandler _commandHandler;
    bool _connected;
    unsigned long _lastReconnectAttempt;

    static void _mqttCallback(char* topic, byte* payload, unsigned int length);
    void _reconnect();
    String _topic(const char* suffix);

    // 全局实例指针（用于静态回调）
    static IoTDevice* _instance;
};

#endif
