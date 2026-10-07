#pragma once

#include <Arduino.h>
#include "esp_camera.h"

// OV2640 capture on the AI-Thinker ESP32-CAM pin map.
namespace camera {

// Initialises the sensor. Returns false when no camera is detected.
bool begin();
bool ready();
bool hasPsram();

// Returns a settled frame, discarding the stale buffers kept after any settings
// change. The caller must pass the result to release(). Returns nullptr on failure.
camera_fb_t* capture();
void release(camera_fb_t* frame);

bool setFrameSize(const String& name);
bool setQuality(int quality);
// Locks aec/agc/awb at their current values so lighting stays consistent
// between captures. Unlocking restores full automatic control.
bool setExposureLock(bool lock);

bool exposureLocked();
int quality();
const char* resolution();
const char* frameSizeName();

}  // namespace camera
