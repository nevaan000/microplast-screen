#include "network.h"

#include <ESPmDNS.h>
#include <WiFi.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define DEVICE_NAME "microplast-cam"
#endif

namespace {
unsigned long nextRetryMs = 0;
}

void networkBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  for (int attempt = 0; WiFi.status() != WL_CONNECTED && attempt < 75; ++attempt) {
    delay(400);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    MDNS.begin(DEVICE_NAME);
    Serial.printf("Ready: http://%s/ and http://%s.local/\n", WiFi.localIP().toString().c_str(), DEVICE_NAME);
  } else {
    Serial.println("Wi-Fi unavailable; the watchdog will retry.");
  }
}

void networkMaintain() {
  if (WiFi.status() == WL_CONNECTED || millis() < nextRetryMs) return;
  nextRetryMs = millis() + 5000;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

String networkIp() { return WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : ""; }
