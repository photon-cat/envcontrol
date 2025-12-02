// STM32F103 "Blue Pill" RS485 test sketch
// Configures FET outputs, DIP switch inputs, and drives RS485 at 500 kbaud.

#include <Arduino.h>

constexpr uint32_t RS485_BAUD = 500000;

// RS485 transceiver control pins
constexpr uint8_t RS485_RX_PIN = PA3;
constexpr uint8_t RS485_TX_PIN = PA2;
constexpr uint8_t RS485_DE_PIN = PA1;
constexpr uint8_t RS485_RE_PIN = PA0;  // Active low receive enable

// Some board configurations do not predefine Serial2; create it if needed.
#if !defined(HAVE_HWSERIAL2)
HardwareSerial Serial2(RS485_RX_PIN, RS485_TX_PIN);
#endif

constexpr uint8_t LED_PIN = LED_BUILTIN;  // On Blue Pill this is PC13 (active low)

// FET outputs
const uint8_t FET_PINS[] = {
  PB0,  // FET_0
  PB1,  // FET_1
  PB3,  // FET_2
  PB4,  // FET_3
  PB5,  // FET_4
  PB6,  // FET_5
  PB7,  // FET_6
  PB8   // FET_7
};

// DIP switch inputs (assumed active low to ground)
const uint8_t DIP_PINS[] = {
  PA4,  // DIP0
  PA5,  // DIP1
  PA6,  // DIP2
  PA7,  // DIP3
  PC14  // DIP4
};

void beginRs485()
{
  pinMode(RS485_DE_PIN, OUTPUT);
  pinMode(RS485_RE_PIN, OUTPUT);
  // Idle with driver enabled and receiver enabled (keeps bus driven for measurement)
  digitalWrite(RS485_DE_PIN, HIGH);
  digitalWrite(RS485_RE_PIN, LOW);

  // Make the pin selection explicit even though these are the defaults
  Serial2.setTx(RS485_TX_PIN);
  Serial2.setRx(RS485_RX_PIN);
  Serial2.begin(RS485_BAUD);
}

void sendRs485(const char *msg)
{
  // Pulse the LED while sending (active-low on PC13)
  digitalWrite(LED_PIN, LOW);

  Serial2.print(msg);
  Serial2.print("\r\n");
  Serial2.flush();

  // Keep driver asserted so A/B stay biased; receiver stays enabled
  digitalWrite(RS485_DE_PIN, HIGH);
  digitalWrite(RS485_RE_PIN, LOW);
  digitalWrite(LED_PIN, HIGH);
}

void setup()
{
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // idle off (active-low LED)

  // Configure FET outputs and default them off
  for (uint8_t pin : FET_PINS) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);
  }

  // Configure DIP switches with pull-ups
  for (uint8_t pin : DIP_PINS) {
    pinMode(pin, INPUT_PULLUP);
  }

  beginRs485();
}

void loop()
{
  static uint32_t lastTx = 0;
  const uint32_t now = millis();

  if (now - lastTx >= 200) {  // 5 Hz
    lastTx = now;
    sendRs485("RS485 test message @500000 baud");
  }
}
