#pragma once

#include <Arduino.h>

// Chamber illumination. Drives the on-board flash LED and, optionally, an
// external LED driver so the sample can be lit evenly instead of from a single
// point source directly above the filter.
namespace led {

// externalPin may be -1 to leave the external driver unconnected.
void begin(int onboardPin, int externalPin);
void setLevel(uint8_t level);
uint8_t level();
bool externalAttached();

}  // namespace led
