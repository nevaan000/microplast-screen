#include "led.h"

// LEDC_CHANNEL_* come from the ESP-IDF driver header; Arduino.h alone does not
// expose them, and esp32-hal-ledc.h does not define them either.
#include "driver/ledc.h"

namespace {

// LEDC channel 0 and timer 0 are reserved for the camera XCLK.
constexpr uint8_t ONBOARD_CHANNEL = LEDC_CHANNEL_1;
constexpr uint8_t EXTERNAL_CHANNEL = LEDC_CHANNEL_2;
// 5 kHz is far above any OV2640 exposure time, so PWM banding does not appear.
constexpr uint32_t PWM_FREQUENCY_HZ = 5000;
constexpr uint8_t PWM_RESOLUTION_BITS = 8;

int externalPin = -1;
uint8_t currentLevel = 0;

}  // namespace

namespace led {

void begin(int onboardPin, int external) {
  ledcSetup(ONBOARD_CHANNEL, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
  ledcAttachPin(onboardPin, ONBOARD_CHANNEL);

  externalPin = external;
  if (externalPin >= 0) {
    ledcSetup(EXTERNAL_CHANNEL, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
    ledcAttachPin(externalPin, EXTERNAL_CHANNEL);
  }
  setLevel(0);
}

void setLevel(uint8_t level) {
  currentLevel = level;
  // Both drivers are active-high: the on-board flash LED and a low-side
  // logic-level MOSFET switching the external LED string to ground.
  ledcWrite(ONBOARD_CHANNEL, currentLevel);
  if (externalPin >= 0) {
    ledcWrite(EXTERNAL_CHANNEL, currentLevel);
  }
}

uint8_t level() { return currentLevel; }

bool externalAttached() { return externalPin >= 0; }

}  // namespace led
