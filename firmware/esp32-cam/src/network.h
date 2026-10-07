#pragma once

#include <Arduino.h>

// Wi-Fi station link plus the mDNS name used to reach the camera.
namespace network {

// Connects and advertises `<hostname>.local`. Returns false if credentials are empty.
bool begin(const char* ssid, const char* password, const char* hostname);

// Reconnect watchdog. Call from loop(): retries with exponential backoff and
// restarts the board when the link stays down too long.
void maintain();

bool connected();
long rssi();
String address();
const char* hostname();

}  // namespace network
