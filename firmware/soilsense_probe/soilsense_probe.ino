// SoilSense ZM probe firmware (spec 2.3, track B).
//
// Arduino Uno with:
//   - analogue pH board on A0 (PH-4502C, DFRobot SEN0161 or similar)
//   - capacitive soil moisture sensor v1.2 on A1
//   - DS18B20 waterproof temperature probe on D2 (4.7 kOhm pull-up to 5 V)
//
// The firmware only measures. It does no calibration and no pH maths: the
// laptop bridge (bridge/bridge.py) turns volts into pH using the calibration
// stored on the server, so a single place holds the calibration history.
//
// Protocol (9600 baud, one command per line, one JSON reply per line):
//   P   -> {"ok":true,"fw":"1.0"}                       ping
//   R   -> {"ok":true,"ph_v":2.512,"moist_raw":512,"temp_c":24.6,"n":40}
//   An error gives {"ok":false,"error":"..."}.
//
// Libraries (Arduino IDE > Tools > Manage Libraries):
//   "OneWire" by Paul Stoffregen, "DallasTemperature" by Miles Burton.

#include <OneWire.h>
#include <DallasTemperature.h>

const char FW_VERSION[] = "1.0";
const uint8_t PIN_PH = A0;
const uint8_t PIN_MOISTURE = A1;
const uint8_t PIN_DS18B20 = 2;

// Board reference voltage. Measure the Uno's 5 V pin with a multimeter and
// put the real value here for better accuracy (often 4.9 to 5.1 V).
const float VREF = 5.00;
const int SAMPLES = 40;          // readings per measurement; the middle half is averaged

OneWire oneWire(PIN_DS18B20);
DallasTemperature tempSensor(&oneWire);

void setup() {
  Serial.begin(9600);
  tempSensor.begin();
  tempSensor.setResolution(12);
}

// Read an analogue pin SAMPLES times, sort, and average the middle half.
// This rejects the spikes that pH boards often show.
float readAnalogTrimmed(uint8_t pin) {
  int values[SAMPLES];
  for (int i = 0; i < SAMPLES; i++) {
    values[i] = analogRead(pin);
    delay(10);
  }
  for (int i = 1; i < SAMPLES; i++) {           // insertion sort, SAMPLES is small
    int key = values[i];
    int j = i - 1;
    while (j >= 0 && values[j] > key) {
      values[j + 1] = values[j];
      j--;
    }
    values[j + 1] = key;
  }
  long sum = 0;
  for (int i = SAMPLES / 4; i < SAMPLES - SAMPLES / 4; i++) {
    sum += values[i];
  }
  return (float)sum / (SAMPLES / 2);
}

void replyReading() {
  tempSensor.requestTemperatures();
  float tempC = tempSensor.getTempCByIndex(0);
  float phRaw = readAnalogTrimmed(PIN_PH);
  float moistRaw = readAnalogTrimmed(PIN_MOISTURE);

  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println(F("{\"ok\":false,\"error\":\"DS18B20 not found: check wiring and the 4.7k pull-up\"}"));
    return;
  }
  float phVolts = phRaw * VREF / 1023.0;

  Serial.print(F("{\"ok\":true,\"ph_v\":"));
  Serial.print(phVolts, 4);
  Serial.print(F(",\"moist_raw\":"));
  Serial.print(moistRaw, 0);
  Serial.print(F(",\"temp_c\":"));
  Serial.print(tempC, 2);
  Serial.print(F(",\"n\":"));
  Serial.print(SAMPLES);
  Serial.println(F("}"));
}

void loop() {
  if (!Serial.available()) return;
  String command = Serial.readStringUntil('\n');
  command.trim();
  if (command == "P") {
    Serial.print(F("{\"ok\":true,\"fw\":\""));
    Serial.print(FW_VERSION);
    Serial.println(F("\"}"));
  } else if (command == "R") {
    replyReading();
  } else if (command.length() > 0) {
    Serial.println(F("{\"ok\":false,\"error\":\"unknown command\"}"));
  }
}
