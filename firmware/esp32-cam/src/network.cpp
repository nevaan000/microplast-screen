#include "network.h"

#include <ESPmDNS.h>
#include <WiFi.h>
#include "esp_system.h"

namespace {

constexpr unsigned long MIN_BACKOFF_MS = 1000;
constexpr unsigned long MAX_BACKOFF_MS = 30000;
// A camera that cannot reach the network is useless in the imaging chamber and
// is usually stuck after an access-point change, so recover by rebooting.
constexpr unsigned long RESTART_AFTER_MS = 120000;

char mdnsHostname[64] = "microplast-cam";
unsigned long nextAttemptAt = 0;
unsigned long backoffMs = MIN_BACKOFF_MS;
unsigned long downSince = 0;
bool wasConnected = false;

}  // namespace

namespace network {

bool begin(const char* ssid, const char* password, const char* hostname) {
  if (!ssid || ssid[0] == '\0') {
    Serial.println("[wifi] WIFI_SSID is empty; edit firmware/esp32-cam/include/secrets.h");
    return false;
  }

  snprintf(mdnsHostname, sizeof(mdnsHostname), "%s", hostname && hostname[0] ? hostname : "microplast-cam");

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(mdnsHostname);
  // Modem sleep adds latency to captures and can drop the link under LED load.
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  Serial.printf("[wifi] connecting to %s", ssid);
  const unsigned long deadline = millis() + 30000;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(400);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[wifi] connection failed; check secrets.h, signal, and the 2.4 GHz band.");
    downSince = millis();
    return false;
  }

  wasConnected = true;
  if (MDNS.begin(mdnsHostname)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("[wifi] mDNS name %s.local registered\n", mdnsHostname);
  } else {
    Serial.println("[wifi] mDNS registration failed; use the IP address instead.");
  }
  Serial.printf("[wifi] connected, address %s\n", WiFi.localIP().toString().c_str());
  return true;
}

void maintain() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wasConnected) {
      wasConnected = true;
      backoffMs = MIN_BACKOFF_MS;
      Serial.printf("[wifi] reconnected, address %s\n", WiFi.localIP().toString().c_str());
      if (mdnsHostname[0]) {
        MDNS.begin(mdnsHostname);
      }    }
    return;
  }

  wasConnected = false;
  const unsigned long now = millis();
  if (downSince == 0) {
    downSince = now;
  } else if (now - downSince > RESTART_AFTER_MS) {
    Serial.println("[wifi] link down too long; restarting the camera.");
    delay(50);
    ESP.restart();
  }

  if (now < nextAttemptAt) {
    return;
  }
  Serial.printf("[wifi] link down, reconnecting (backoff %lu ms)\n", backoffMs);
  WiFi.disconnect();
  WiFi.reconnect();
  nextAttemptAt = now + backoffMs;
  backoffMs = backoffMs < MAX_BACKOFF_MS ? min(backoffMs * 2, MAX_BACKOFF_MS) : MAX_BACKOFF_MS;
}

bool connected() { return WiFi.status() == WL_CONNECTED; }

long rssi() { return connected() ? WiFi.RSSI() : 0; }

String address() { return connected() ? WiFi.localIP().toString() : String("disconnected"); }

const char* hostname() { return mdnsHostname; }

}  // namespace network
