/**
 * 智能风扇控制示例 — ESP32 + 继电器 + PWM
 *
 * 硬件连接:
 *   继电器 VCC → 3.3V
 *   继电器 GND → GND
 *   继电器 IN → GPIO5
 *   风扇 PWM → GPIO18
 *
 * 使用前:
 *   1. 在平台创建设备 fan-01（类型: smart_fan）
 *   2. 修改 WIFI_SSID, WIFI_PASS, BROKER
 */

#include <WiFi.h>
#include <IoTDevice.h>

// ── 配置 ──
#define WIFI_SSID  "your-wifi-ssid"
#define WIFI_PASS  "your-wifi-password"
#define BROKER     "192.168.1.100"
#define DEVICE_ID  "fan-01"
#define RELAY_PIN  5
#define PWM_PIN    18
#define PWM_FREQ   25000
#define PWM_CH     0
#define PWM_RES    10  // 10 位分辨率 (0-1023)

// ── 初始化 ──
IoTDevice device(DEVICE_ID, BROKER);

String fanPower = "off";
int fanSpeed = 0;
unsigned long lastReport = 0;

void setFan(String power, int speed = 0) {
    fanPower = power;
    fanSpeed = speed;

    if (power == "on") {
        digitalWrite(RELAY_PIN, HIGH);
        int duty = speed * 205;  // speed 1-5 → duty 205-1023
        ledcWrite(PWM_CH, min(duty, 1023));
    } else {
        digitalWrite(RELAY_PIN, LOW);
        ledcWrite(PWM_CH, 0);
    }

    // 上报新状态到平台影子
    StaticJsonDocument<64> shadow;
    shadow["power"] = fanPower;
    shadow["speed"] = fanSpeed;
    device.reportShadow(shadow);

    Serial.printf("风扇: power=%s, speed=%d\n", fanPower.c_str(), fanSpeed);
}

void onCommand(JsonDocument& cmd) {
    Serial.print("收到命令: ");
    serializeJson(cmd, Serial);
    Serial.println();

    if (cmd.containsKey("power")) {
        String power = cmd["power"].as<String>();
        int speed = cmd.containsKey("speed") ? cmd["speed"].as<int>() : fanSpeed;
        if (power == "on" || power == "off") {
            setFan(power, power == "on" ? speed : 0);
        }
    }
}

void setup() {
    Serial.begin(115200);

    // 初始化 GPIO
    pinMode(RELAY_PIN, OUTPUT);
    ledcSetup(PWM_CH, PWM_FREQ, PWM_RES);
    ledcAttachPin(PWM_PIN, PWM_CH);
    ledcWrite(PWM_CH, 0);

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

    // 每 8 秒上报状态
    if (millis() - lastReport > 8000) {
        StaticJsonDocument<64> doc;
        doc["power"] = fanPower;
        doc["speed"] = fanSpeed;
        doc["mode"] = "normal";
        device.report(doc);
        lastReport = millis();
    }
}
