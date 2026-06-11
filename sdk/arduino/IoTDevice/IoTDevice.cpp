/**
 * IoT Platform 设备接入 SDK — Arduino 实现
 */

#include "IoTDevice.h"

IoTDevice* IoTDevice::_instance = nullptr;

IoTDevice::IoTDevice(const char* deviceId, const char* broker, int port)
    : _deviceId(deviceId), _broker(broker), _port(port),
      _mqttClient(_wifiClient), _commandHandler(nullptr),
      _connected(false), _lastReconnectAttempt(0) {
    _instance = this;
}

bool IoTDevice::connect() {
    _mqttClient.setServer(_broker, _port);
    _mqttClient.setCallback(_mqttCallback);
    _mqttClient.setBufferSize(512);

    // 设置 LWT
    String willTopic = _topic("status");
    String willPayload = "{\"status\":\"offline\",\"reason\":\"connection_lost\"}";

    if (_mqttClient.connect(_deviceId, NULL, NULL,
                            willTopic.c_str(), 1, true,
                            willPayload.c_str())) {
        // 订阅命令主题
        String cmdTopic = _topic("commands");
        _mqttClient.subscribe(cmdTopic.c_str());

        // 发布上线状态
        String statusTopic = _topic("status");
        _mqttClient.publish(statusTopic.c_str(), "{\"status\":\"online\"}", true);

        _connected = true;
        Serial.printf("[%s] 已连接到 %s:%d\n", _deviceId, _broker, _port);
        return true;
    } else {
        Serial.printf("[%s] 连接失败, rc=%d\n", _deviceId, _mqttClient.state());
        _connected = false;
        return false;
    }
}

void IoTDevice::report(const char* jsonPayload) {
    String topic = _topic("telemetry");
    _mqttClient.publish(topic.c_str(), jsonPayload);
}

void IoTDevice::report(const String& jsonPayload) {
    report(jsonPayload.c_str());
}

void IoTDevice::report(JsonDocument& doc) {
    String payload;
    serializeJson(doc, payload);
    report(payload);
}

void IoTDevice::reportShadow(const char* jsonPayload) {
    String topic = _topic("state/reported");
    _mqttClient.publish(topic.c_str(), jsonPayload, true);
}

void IoTDevice::onCommand(CommandHandler handler) {
    _commandHandler = handler;
}

void IoTDevice::tick() {
    if (!_mqttClient.connected()) {
        _connected = false;
        _reconnect();
    }
    _mqttClient.loop();
}

bool IoTDevice::isConnected() {
    return _connected && _mqttClient.connected();
}

void IoTDevice::disconnect() {
    String statusTopic = _topic("status");
    _mqttClient.publish(statusTopic.c_str(), "{\"status\":\"offline\",\"reason\":\"manual\"}", true);
    _mqttClient.disconnect();
    _connected = false;
}

void IoTDevice::_mqttCallback(char* topic, byte* payload, unsigned int length) {
    if (_instance == nullptr || _instance->_commandHandler == nullptr) return;

    // 检查是否是命令主题
    String cmdTopic = _instance->_topic("commands");
    if (String(topic) == cmdTopic) {
        // 解析 JSON
        StaticJsonDocument<512> doc;
        DeserializationError error = deserializeJson(doc, payload, length);
        if (!error) {
            _instance->_commandHandler(doc);
        }
    }
}

void IoTDevice::_reconnect() {
    unsigned long now = millis();
    if (now - _lastReconnectAttempt < 5000) return;  // 5 秒重试间隔
    _lastReconnectAttempt = now;

    Serial.printf("[%s] 尝试重连...\n", _deviceId);
    connect();
}

String IoTDevice::_topic(const char* suffix) {
    return String("devices/") + _deviceId + "/" + suffix;
}
