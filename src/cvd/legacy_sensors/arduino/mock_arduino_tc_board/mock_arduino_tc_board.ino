#include <Arduino.h>

// Pins match the original TC board but can be adjusted as needed
const uint8_t LED1_PIN = 30;
const uint8_t LED2_PIN = 40;
const uint8_t RELAY_PIN = 54;

static const uint8_t MAX_SENSORS = 8;
uint8_t sensorIds[MAX_SENSORS];
uint8_t numSensors = 0;

// optional parameters simply stored for completeness
float sensorOffsets[MAX_SENSORS];
float alpha = 0.1f;
bool smoothing = false;
bool loggingEnabled = false;

void logMsg(const String &msg) {
    if (loggingEnabled) Serial.println(msg);
}

void setup() {
    pinMode(LED1_PIN, OUTPUT);
    pinMode(LED2_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);

    Serial.begin(9600);
    while (!Serial) {
        ;
    }
    randomSeed(analogRead(0));
    Serial.println("=== Mock Arduino TCBoard Ready ===");
    Serial.println("Type 'HELP' for available commands");
}

float generateTemperature(uint8_t idx) {
    float base = random(2000, 3000) / 100.0; // 20.00 – 30.00 °C
    return base + sensorOffsets[idx];
}

void handleCommand(String cmd) {
    if (cmd.startsWith("S")) {
        numSensors = 0;
        int start = 2;
        while (start < cmd.length() && numSensors < MAX_SENSORS) {
            int sep = cmd.indexOf(',', start);
            if (sep == -1) sep = cmd.length();
            sensorIds[numSensors] = cmd.substring(start, sep).toInt();
            sensorOffsets[numSensors] = 0.0f;
            start = sep + 1;
            numSensors++;
        }
        Serial.println("OK");
    } else if (cmd.startsWith("R")) {
        int idx = cmd.substring(1).toInt();
        if (idx < numSensors) {
            float t = generateTemperature(idx);
            Serial.println(t, 2);
        } else {
            Serial.println("ERR");
            digitalWrite(LED1_PIN, HIGH);
        }
    } else if (cmd == "LED1_ON") {
        digitalWrite(LED1_PIN, HIGH);
        Serial.println("OK");
    } else if (cmd == "LED1_OFF") {
        digitalWrite(LED1_PIN, LOW);
        Serial.println("OK");
    } else if (cmd == "LED2_ON") {
        digitalWrite(LED2_PIN, HIGH);
        Serial.println("OK");
    } else if (cmd == "LED2_OFF") {
        digitalWrite(LED2_PIN, LOW);
        Serial.println("OK");
    } else if (cmd == "RELAY_ON") {
        digitalWrite(RELAY_PIN, HIGH);
        Serial.println("OK");
    } else if (cmd == "RELAY_OFF") {
        digitalWrite(RELAY_PIN, LOW);
        Serial.println("OK");
    } else if (cmd == "LOG_ON") {
        loggingEnabled = true;
        Serial.println("Logging enabled");
    } else if (cmd == "LOG_OFF") {
        loggingEnabled = false;
        Serial.println("Logging disabled");
    } else if (cmd.startsWith("ALPHA=")) {
        alpha = cmd.substring(6).toFloat();
        Serial.println("OK");
    } else if (cmd.startsWith("OFFSET=")) {
        int sep = cmd.indexOf(',');
        if (sep > 7 && sep < cmd.length() - 1) {
            int idx = cmd.substring(7, sep).toInt();
            float off = cmd.substring(sep + 1).toFloat();
            if (idx < numSensors) {
                sensorOffsets[idx] = off;
                Serial.println("OK");
            } else {
                Serial.println("ERR");
            }
        } else {
            Serial.println("ERR");
        }
    } else if (cmd == "SMOOTHING_ON") {
        smoothing = true;
        Serial.println("OK");
    } else if (cmd == "SMOOTHING_OFF") {
        smoothing = false;
        Serial.println("OK");
    } else if (cmd == "DEBUG") {
        Serial.print("Sensors: ");
        Serial.println(numSensors);
        for (uint8_t i = 0; i < numSensors; ++i) {
            Serial.print("S[");
            Serial.print(i);
            Serial.print("] id ");
            Serial.print(sensorIds[i]);
            Serial.print(" -> ");
            Serial.println(generateTemperature(i), 2);
        }
    } else if (cmd == "HELP") {
        Serial.println("Mock commands: S, R#, LED1_ON, LED1_OFF, LED2_ON, LED2_OFF, RELAY_ON, RELAY_OFF");
    }
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        handleCommand(cmd);
    }
}
