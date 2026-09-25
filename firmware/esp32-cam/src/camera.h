#pragma once

#include <Arduino.h>
#include "esp_camera.h"

bool cameraBegin();
camera_fb_t* cameraCapture();
void cameraRelease(camera_fb_t* frame);
bool cameraConfigure(const String& frameSize, int quality, bool lockExposure);
String cameraStatusJson();
