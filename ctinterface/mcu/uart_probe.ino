// UART probe sketch for CT2 RS-485 bus experiments
// Features:
//   * USB Serial (115200) command interface
//   * RS-485 Serial1 connected through MAX485 transceiver (receive-only)
//   * Quick switching between multiple UART frame configs (8N1, 8E1, etc.)
//   * Optional auto-cycling to scan through configs
//   * Hex dump output tagged with the active configuration and timestamp
//
// Commands (send via USB serial monitor):
//   HELP            - Print command summary
//   LIST            - Show all predefined configurations
//   SET <index>     - Switch to configuration by index
//   AUTO ON|OFF     - Enable/disable auto-cycling through configs
//   BAUD <value>    - Set custom baud for current config (keeps framing)
//   RESET           - Clear byte counters
//
// Wiring notes
//   RS-485 TX pin: 6  (informational)
//   RS-485 RX pin: 7  (informational)
//   RE/DE tied:   2   (forced LOW for listen-only)

#include <Arduino.h>

#define RS485_TX_PIN 6
#define RS485_RX_PIN 7
#define RE_DE_PIN    2

struct DecoderConfig {
  const char* name;
  uint32_t baud;
  uint16_t serialConfig;
};

DecoderConfig configs[] = {
  {"500k_8N1", 500000, SERIAL_8N1},
  {"500k_8E1", 500000, SERIAL_8E1},
  {"500k_8O1", 500000, SERIAL_8O1},
  {"500k_7E1", 500000, SERIAL_7E1},
  {"500k_8N2", 500000, SERIAL_8N2},
  {"460k8_8N1", 460800, SERIAL_8N1},
  {"460k8_8E1", 460800, SERIAL_8E1}
};

const uint8_t CONFIG_COUNT = sizeof(configs) / sizeof(configs[0]);
uint8_t currentConfig = 0;
bool autoCycle = false;
const unsigned long AUTO_INTERVAL_MS = 3000;
unsigned long lastConfigSwitch = 0;

unsigned long byteCount = 0;
unsigned long lineStart = 0;
bool lineActive = false;
const unsigned long IDLE_LINE_BREAK_MS = 4;

void applyConfig(uint8_t idx) {
  if (idx >= CONFIG_COUNT) return;
  currentConfig = idx;
  Serial1.end();
  delay(2);
  Serial1.begin(configs[currentConfig].baud, configs[currentConfig].serialConfig);
  Serial.print("CONFIG,");
  Serial.print(currentConfig);
  Serial.print(",");
  Serial.println(configs[currentConfig].name);
  Serial.flush();
  lastConfigSwitch = millis();
}

void printConfigList() {
  Serial.println("INDEX,NAME,BAUD,FRAME");
  for (uint8_t i = 0; i < CONFIG_COUNT; i++) {
    Serial.print(i);
    Serial.print(',');
    Serial.print(configs[i].name);
    Serial.print(',');
    Serial.print(configs[i].baud);
    Serial.print(',');
    Serial.println(configs[i].serialConfig, HEX);
  }
  Serial.flush();
}

void printHelp() {
  Serial.println("Commands: HELP | LIST | SET <idx> | AUTO ON|OFF | BAUD <value> | RESET");
  Serial.flush();
}

void handleCommand(const String& input) {
  if (input.length() == 0) return;
  if (input == "HELP") {
    printHelp();
  } else if (input == "LIST") {
    printConfigList();
  } else if (input.startsWith("SET")) {
    int idx = input.substring(3).toInt();
    if (idx >= 0 && idx < CONFIG_COUNT) {
      autoCycle = false;
      applyConfig(idx);
    } else {
      Serial.println("ERR,BAD_INDEX");
      Serial.flush();
    }
  } else if (input.startsWith("AUTO")) {
    if (input.endsWith("ON")) {
      autoCycle = true;
      lastConfigSwitch = 0;
    } else if (input.endsWith("OFF")) {
      autoCycle = false;
    }
    Serial.print("AUTO,");
    Serial.println(autoCycle ? "ON" : "OFF");
    Serial.flush();
  } else if (input.startsWith("BAUD")) {
    unsigned long value = input.substring(4).toInt();
    if (value >= 9600) {
      configs[currentConfig].baud = value;
      applyConfig(currentConfig);
    } else {
      Serial.println("ERR,BAD_BAUD");
      Serial.flush();
    }
  } else if (input == "RESET") {
    byteCount = 0;
    Serial.println("STATUS,RESET");
    Serial.flush();
  } else {
    Serial.println("ERR,UNKNOWN_CMD");
    Serial.flush();
  }
}

void setup() {
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);

  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}
  Serial.println("UART_PROBE_READY");
  printHelp();

  applyConfig(currentConfig);
}

void loop() {
  unsigned long now = millis();

  if (autoCycle && (now - lastConfigSwitch) > AUTO_INTERVAL_MS) {
    uint8_t nextIdx = (currentConfig + 1) % CONFIG_COUNT;
    applyConfig(nextIdx);
  }

  while (Serial1.available() > 0) {
    int value = Serial1.read();
    if (value < 0) continue;

    if (!lineActive) {
      Serial.print("DATA,");
      Serial.print(configs[currentConfig].name);
      Serial.print(",");
      Serial.print(now);
      Serial.print(",");
      lineStart = now;
      lineActive = true;
    }

    if (value < 0x10) Serial.print("0");
    Serial.print(value, HEX);
    Serial.print(' ');
    byteCount++;
  }

  if (lineActive && (millis() - lineStart) > IDLE_LINE_BREAK_MS) {
    Serial.println();
    Serial.flush();
    lineActive = false;
  }

  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();
    handleCommand(cmd);
  }
}
