#include <math.h>

#define SERIES_RESISTOR     100000.0
#define NOMINAL_RESISTANCE  100000.0
#define NOMINAL_TEMPERATURE 25.0
#define B_COEFFICIENT       3950.0

bool debugEnabled = false;

// Outputs log messages to the serial monitor if debugging is enabled
void log(const String& msg) {
    if (debugEnabled) Serial.println(msg);
}

class TemperatureSensor {
private:
    float offset = 0.0;
public:
    bool smoothingEnabled = false;
private:
    float alpha = 0.1; // EMA smoothing factor, adjustable
    float lastTemperature = NAN;
    uint8_t analogPin;
    float seriesResistor;
    float nominalResistance;
    float nominalTemperature;
    float betaCoefficient;

public:
        // Sets the temperature offset for calibration
    void setOffset(float newOffset) {
        offset = newOffset;
    }

    // Sets the exponential smoothing factor (alpha) for EMA
    void setAlpha(float newAlpha) {
        if (newAlpha >= 0.0 && newAlpha <= 1.0) {
            alpha = newAlpha;
        }
    }

        // Constructor initializes the temperature sensor with physical and thermistor parameters
    TemperatureSensor(uint8_t pin, float seriesRes, float nominalRes, float nominalTemp, float beta)
        : analogPin(pin), seriesResistor(seriesRes), nominalResistance(nominalRes),
          nominalTemperature(nominalTemp), betaCoefficient(beta) {}

        // Reads and returns the smoothed temperature in Celsius using EMA filtering
    // Reads and returns temperature in Celsius, optionally using EMA
    float readTemperatureCelsius() {
        int analogValue = analogRead(analogPin);
        log("Analog value (pin " + String(analogPin) + "): " + String(analogValue));
        if (analogValue <= 0) return -273.15;

        float voltage = analogValue * (5.0 / 1023.0);
        log("Voltage: " + String(voltage, 3));
        float resistance = (seriesResistor * voltage) / (5.0 - voltage);
        log("Resistance: " + String(resistance, 2));
        float steinhart = resistance / nominalResistance;
        steinhart = log(steinhart);
        steinhart /= betaCoefficient;
        steinhart += 1.0 / (nominalTemperature + 273.15);
        steinhart = 1.0 / steinhart;
        float currentTemp = steinhart - 273.15;

        if (!smoothingEnabled) {
            lastTemperature = currentTemp;
        } else if (isnan(lastTemperature)) {
            lastTemperature = currentTemp;
        } else {
            lastTemperature = alpha * currentTemp + (1 - alpha) * lastTemperature;
        }

        return lastTemperature + offset;
    }

        // Returns the analog pin associated with this sensor
    uint8_t getPin() const {
        return analogPin;
    }
};

class ArduinoTCBoard {
private:
    static const uint8_t maxSensors = 8;
    TemperatureSensor* sensors[maxSensors];
    uint8_t sensorPins[maxSensors];
    uint8_t numSensors;

    uint8_t led1Pin;
    uint8_t led2Pin;
    uint8_t relayPin;

public:
        // Constructor initializes the board with given LED and relay control pins
    ArduinoTCBoard(uint8_t l1, uint8_t l2, uint8_t rPin)
        : led1Pin(l1), led2Pin(l2), relayPin(rPin), numSensors(0) {
        for (uint8_t i = 0; i < maxSensors; ++i) sensors[i] = nullptr;
    }

        // Initializes serial communication and configures pin modes
    void begin() {
        
        while (!Serial);  // Wait for Serial Monitor to open (optional)
        pinMode(led1Pin, OUTPUT);
        pinMode(led2Pin, OUTPUT);
        pinMode(relayPin, OUTPUT);
        Serial.begin(9600);
        analogReference(DEFAULT);
        Serial.println("=== Arduino TCBoard Ready ===");
        Serial.println("Type 'HELP' for available commands");
        digitalWrite(led2Pin, HIGH); // Turn on serial status LED
    }

        // Configures up to 8 temperature sensors using provided analog pin numbers
    void configureSensors(const uint8_t* pins, uint8_t count) {
        for (uint8_t i = 0; i < maxSensors; ++i) {
            delete sensors[i];
            sensors[i] = nullptr;
        }
        numSensors = 0;
        for (uint8_t i = 0; i < count && numSensors < maxSensors; ++i) {
            if (isAllowedSensorPin(pins[i])) {
                sensorPins[numSensors] = pins[i];
                sensors[numSensors] = new TemperatureSensor(
                    pins[i],
                    SERIES_RESISTOR,
                    NOMINAL_RESISTANCE,
                    NOMINAL_TEMPERATURE,
                    B_COEFFICIENT
                );
                log("Accepted pin: " + String(pins[i]));
                numSensors++;
            }
        }
        log("Sensors configured");
    }

        // Polls serial for new commands and updates temperature state of all sensors
    void update() {
        handleSerial();
        // update temperature state silently for all sensors
        for (uint8_t i = 0; i < numSensors; ++i) {
            if (sensors[i]) sensors[i]->readTemperatureCelsius();
        }
    }

        // Parses and executes serial commands for configuration and interaction
    void handleSerial() {
        if (Serial.available()) {
            String command = Serial.readStringUntil('\n');
            command.trim();

            if (command.startsWith("S")) {
                uint8_t pins[maxSensors];
                uint8_t index = 0;
                int start = 2;
                while (index < maxSensors) {
                    int comma = command.indexOf(',', start);
                    if (comma == -1) comma = command.length();
                    String pinStr = command.substring(start, comma);
                    uint8_t pin = analogPinFromString(pinStr);
                    if (pin != 255) {
                        pins[index++] = pin;
                    }
                    start = comma + 1;
                    if (start >= command.length()) break;
                }
                configureSensors(pins, index);

            } else if (command.startsWith("R")) {
                uint8_t idx = command.substring(1).toInt();
                if (idx < numSensors && sensors[idx]) {
                    float temp = sensors[idx]->readTemperatureCelsius();
                    log("Sensor index " + String(idx) + " read: " + String(temp, 2));
                    Serial.println(temp, 2);
                } else {
                    log("Invalid read request for index " + String(idx));
                    Serial.println("ERR");
                    digitalWrite(led1Pin, HIGH); // turn on LED1 on error
                    static unsigned long errorTime = millis();
                    errorTime = millis();
                }
            } else if (command == "DEBUG") {
                Serial.println("=== DEBUG INFO ===");
                Serial.print("Configured sensors: "); Serial.println(numSensors);
                for (uint8_t i = 0; i < numSensors; ++i) {
                    if (sensors[i]) {
                        float temp = sensors[i]->readTemperatureCelsius();
                        Serial.print("Sensor["); Serial.print(i); Serial.print("] on pin ");
                        Serial.print(sensors[i]->getPin());
                        Serial.print(" → Temp: "); Serial.println(temp, 2);
                    }
                }
                Serial.print("LED1 Status: "); Serial.println(digitalRead(led1Pin) ? "ON" : "OFF");
                Serial.print("LED2 Status: "); Serial.println(digitalRead(led2Pin) ? "ON" : "OFF");
                Serial.print("Relay Status: "); Serial.println(digitalRead(relayPin) ? "ON" : "OFF");
                Serial.print("LOG Status: "); Serial.println(debugEnabled ? "ENABLED" : "DISABLED");
                Serial.print("Smoothing Status: ");
                if (numSensors > 0 && sensors[0]) {
                    Serial.println(sensors[0]->smoothingEnabled ? "ENABLED" : "DISABLED");
                } else {
                    Serial.println("UNKNOWN");
                }
                Serial.println("==================");
            } else if (command == "LOG_ON") {
                debugEnabled = true;
                Serial.println("Logging enabled");
            } else if (command == "LOG_OFF") {
                debugEnabled = false;
                Serial.println("Logging disabled");
            } else if (command == "LED1_ON") {
                digitalWrite(led1Pin, HIGH);
            } else if (command == "LED1_OFF") {
                digitalWrite(led1Pin, LOW);
            } else if (command == "LED2_ON") {
                digitalWrite(led2Pin, HIGH);
            } else if (command == "LED2_OFF") {
                digitalWrite(led2Pin, LOW);
            } else if (command == "RELAY_ON") {
                digitalWrite(relayPin, HIGH);
                return; // prevent sensor read fallback else if (command == "RELAY_OFF") {
                digitalWrite(relayPin, LOW);
                return; // prevent sensor read fallback else if (command.startsWith("ALPHA=")) {
                float newAlpha = command.substring(6).toFloat();
                for (uint8_t i = 0; i < numSensors; ++i) {
                    if (sensors[i]) sensors[i]->setAlpha(newAlpha);
                }
                Serial.print("Alpha set to: "); Serial.println(newAlpha);
            } else if (command == "RESET") {
                Serial.println("Resetting...");
                delay(100);
                asm volatile ("jmp 0");
            } else if (command == "POWER_OFF") {
                Serial.println("Powering off (simulate)");
                digitalWrite(led1Pin, LOW);
                digitalWrite(led2Pin, LOW);
                digitalWrite(relayPin, LOW);
                // Optionally: go into low power mode (only on supported boards)
            } else if (command == "SMOOTHING_ON") {
                for (uint8_t i = 0; i < numSensors; ++i) {
                    if (sensors[i]) sensors[i]->smoothingEnabled = true;
                }
                Serial.println("Smoothing enabled");
            } else if (command == "SMOOTHING_OFF") {
                for (uint8_t i = 0; i < numSensors; ++i) {
                    if (sensors[i]) sensors[i]->smoothingEnabled = false;
                }
                Serial.println("Smoothing disabled");
            } else if (command.startsWith("OFFSET=")) {
                int sep = command.indexOf(',');
                if (sep > 7 && sep < command.length() - 1) {
                    int sensorIndex = command.substring(7, sep).toInt();
                    float offsetValue = command.substring(sep + 1).toFloat();
                    if (sensorIndex < numSensors && sensors[sensorIndex]) {
                        sensors[sensorIndex]->setOffset(offsetValue);
                        Serial.print("Offset for sensor "); Serial.print(sensorIndex);
                        Serial.print(" set to: "); Serial.println(offsetValue);
                    } else {
                        Serial.println("ERR");
                        digitalWrite(led1Pin, HIGH);
                    }
                } else {
                    Serial.println("ERR");
                    digitalWrite(led1Pin, HIGH);
                }
            } else if (command == "HELP") {
                Serial.println("=== AVAILABLE COMMANDS ===");
                Serial.println("S,0,1,... or S,A1,A2,...  → Set active analog pins for sensors (max 8)");
                Serial.println("R0,R1,...     → Read temperature from sensor index (0–7)");
                Serial.println("ALPHA=0.1     → Set EMA smoothing factor (0.0–1.0)");
                Serial.println("DEBUG         → Print all sensor readings and pins");
                Serial.println("LOG_ON        → Enable serial logging");
                Serial.println("LOG_OFF       → Disable serial logging");
                Serial.println("LED1_ON       → Turn on LED1");
                Serial.println("LED1_OFF      → Turn off LED1");
                Serial.println("LED2_ON       → Turn on LED2");
                Serial.println("LED2_OFF      → Turn off LED2");
                Serial.println("RELAY_ON      → Activate relay output");
                Serial.println("RELAY_OFF     → Deactivate relay output");
                Serial.println("RESET         → Software reset of the board");
                Serial.println("POWER_OFF     → Simulated power-down (all outputs off)");
                Serial.println("SMOOTHING_ON     → Enable EMA smoothing for temperature readings");
                Serial.println("SMOOTHING_OFF    → Disable EMA smoothing and return absolute temperature");
                Serial.println("OFFSET=idx,value → Calibrate sensor by adding value (°C) to its reading");
                Serial.println("===========================");
            }
        }
    }

        // Converts a string like "A1" to the corresponding analog pin number
    uint8_t analogPinFromString(const String& pinStr) {
        if (pinStr.length() == 1 && isDigit(pinStr.charAt(0))) {
            int index = pinStr.toInt();
            switch (index) {
                case 0: return 55;  // A1
                case 1: return 56;  // A2
                case 2: return 57;  // A3
                case 3: return 58;  // A4
                case 4: return 59;  // A5
                case 5: return 60;  // A6
                case 6: return 61;  // A7
                case 7: return 62;  // A8
                default: return 255;
            }
        } else if (pinStr.length() >= 2 && pinStr.charAt(0) == 'A') {
            int num = pinStr.substring(1).toInt();
            switch (num) {
                case 0: return 55;
                case 1: return 56;
                case 2: return 57;
                case 3: return 58;
                case 4: return 59;
                case 5: return 60;
                case 6: return 61;
                case 7: return 62;
                default: return 255;
            }
        }
        return 255;
    }

        // Validates whether a pin number corresponds to A1–A8 on Arduino Mega
    bool isAllowedSensorPin(uint8_t pin) {
        return pin >= 55 && pin <= 62; // A1 to A8 on Arduino Mega (digital pins 55–62)
    }
};

ArduinoTCBoard board(30, 40, 54);

unsigned long lastUpdate = 0;
const unsigned long updateInterval = 100;

// Arduino setup function; initializes the board
void setup() {
    board.begin();
}

// Arduino main loop; updates board state periodically
void loop() {
    static unsigned long errorLedOnTime = 0;

    // Monitor serial connection status and turn off LED2 if disconnected
    if (!Serial) {
        digitalWrite(40, LOW); // assuming led2Pin is 40
    }

    unsigned long now = millis();
        if (digitalRead(30) == HIGH && errorLedOnTime == 0) {
        errorLedOnTime = millis();
    }
    if (errorLedOnTime > 0 && millis() - errorLedOnTime >= 5000) {
        digitalWrite(30, LOW); // turn off LED1 after 5s
        errorLedOnTime = 0;
    }

    if (now - lastUpdate >= updateInterval) {
        board.update();
        lastUpdate = now;
    }
}