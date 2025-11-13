// SAMD21 + MAX485 passive monitor for byte logging
// USB console: Serial (115200)
// RS-485 bus:  Serial1 (configurable baud)
// DE/RE tied together and held LOW for receive-only mode

// ---- Board pin mapping notes ----
// Seeeduino XIAO (SAMD21): Serial1 TX=D6, RX=D7
// Arduino Zero / MKR family: Serial1 pins are fixed by the core

#define RS485_TX_PIN 6   // Informational only
#define RS485_RX_PIN 7   // Informational only
#define RE_DE_PIN 2      // Connect MAX485 RE+DE together and tie here

// Try different baud rates if 115200 doesn't work
#define RS485_BAUD 500000  // Target bus speed
#define SERIAL_CONFIG SERIAL_8E1
const char* CONFIG_NAME = "500k_8E1";

#define HEX_GROUP_TIMEOUT 5  // ms gap that triggers newline grouping

unsigned long byteCount = 0;
unsigned long lastByteTime = 0;
unsigned long lineStart = 0;
bool lineActive = false;

void setup() {
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW);       // Receive-only mode

  Serial.begin(115200);               // USB CDC to computer
  while (!Serial && millis() < 3000); // Wait up to 3s for Serial Monitor

  Serial.println("LOGGER_READY");     // Signal for Python script
  Serial.flush();

  Serial1.begin(RS485_BAUD, SERIAL_CONFIG);  // RS-485 bus UART
}

void loop() {
  unsigned long now = millis();
  bool printedBytes = false;

  // Read bytes and dump as hex with minimal grouping
  while (Serial1.available() > 0) {
    uint8_t b = Serial1.read();
    unsigned long ts = millis();
    if (!lineActive) {
      Serial.print("DATA,");
      Serial.print(CONFIG_NAME);
      Serial.print(",");
      Serial.print(ts);
      Serial.print(",");
      lineActive = true;
      lineStart = ts;
    }
    if (b < 0x10) Serial.print("0");
    Serial.print(b, HEX);
    Serial.print(" ");
    byteCount++;
    lastByteTime = ts;
    now = ts;
    printedBytes = true;
  }

  now = millis();

  // Close out the current line if we saw data and the bus has been idle
  if (lineActive && (now - lastByteTime) > HEX_GROUP_TIMEOUT) {
    Serial.println();
    Serial.flush();
    lineActive = false;
  } else if (printedBytes) {
    Serial.flush();
  }

  // Handle commands from Serial Monitor
  if (Serial.available()) {
    String raw = Serial.readStringUntil('\n');
    raw.trim();
    if (raw.length() == 0) {
      return;
    }

    String cmd = raw;
    String args = "";
    int spaceIndex = raw.indexOf(' ');
    if (spaceIndex >= 0) {
      cmd = raw.substring(0, spaceIndex);
      args = raw.substring(spaceIndex + 1);
      args.trim();
    }

    String cmdUpper = cmd;
    cmdUpper.toUpperCase();

    if (cmdUpper == "STATS") {
      Serial.print("STATUS,");
      Serial.print(now);
      Serial.print(",BYTES=");
      Serial.print(byteCount);
      Serial.print(",UPTIME=");
      Serial.print(now / 1000);
      Serial.println("s");
      Serial.flush();
    }
    else if (cmdUpper == "RESET") {
      byteCount = 0;
      Serial.println("STATUS,RESET");
      Serial.flush();
    }
    else if (cmdUpper == "NOTE" || cmdUpper == "STATE") {
      Serial.print("NOTE,");
      Serial.print(now);
      Serial.print(",");
      Serial.println(args);
      Serial.flush();
    }
  }
}
