#include "led.h"

namespace {
constexpr int FLASH_LED_PIN = 4;
// GPIO12/13 suit an external transistor driver on many AI-Thinker boards.
// GPIO12 is a boot strapping pin: do not pull it high during reset.
#ifdef EXTERNAL_LED_PIN
constexpr int EXTERNAL_PIN = EXTERNAL_LED_PIN;
#endif
uint8_t level = 0;
}

void ledBegin() {
  ledcSetup(LEDC_CHANNEL_1, 5000, 8);
  ledcAttachPin(FLASH_LED_PIN, LEDC_CHANNEL_1);
#ifdef EXTERNAL_LED_PIN
  ledcSetup(LEDC_CHANNEL_2, 5000, 8);
  ledcAttachPin(EXTERNAL_PIN, LEDC_CHANNEL_2);
#endif
  ledSet(0);
}

void ledSet(uint8_t value) {
  level = value;
  ledcWrite(LEDC_CHANNEL_1, level);
#ifdef EXTERNAL_LED_PIN
  ledcWrite(LEDC_CHANNEL_2, level);
#endif
}

uint8_t ledLevel() { return level; }
