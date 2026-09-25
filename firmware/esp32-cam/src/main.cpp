#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "esp_system.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define DEVICE_NAME "microplast-cam"
#define SERVER_URL ""
#define DEVICE_API_KEY ""
#endif

namespace {
constexpr int PIN_PWDN = 32;
constexpr int PIN_RESET = -1;
constexpr int PIN_XCLK = 0;
constexpr int PIN_SIOD = 26;
constexpr int PIN_SIOC = 27;
constexpr int PIN_Y9 = 35;
constexpr int PIN_Y8 = 34;
constexpr int PIN_Y7 = 39;
constexpr int PIN_Y6 = 36;
constexpr int PIN_Y5 = 21;
constexpr int PIN_Y4 = 19;
constexpr int PIN_Y3 = 18;
constexpr int PIN_Y2 = 5;
constexpr int PIN_VSYNC = 25;
constexpr int PIN_HREF = 23;
constexpr int PIN_PCLK = 22;
constexpr int PIN_LED = 4;

WebServer server(80);
uint8_t ledLevel = 0;
uint32_t startedAt = 0;

void sendJson(int status, const String& body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(status, "application/json", body);
}

bool initCamera() {
  camera_config_t config{};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = PIN_Y2;
  config.pin_d1 = PIN_Y3;
  config.pin_d2 = PIN_Y4;
  config.pin_d3 = PIN_Y5;
  config.pin_d4 = PIN_Y6;
  config.pin_d5 = PIN_Y7;
  config.pin_d6 = PIN_Y8;
  config.pin_d7 = PIN_Y9;
  config.pin_xclk = PIN_XCLK;
  config.pin_pclk = PIN_PCLK;
  config.pin_vsync = PIN_VSYNC;
  config.pin_href = PIN_HREF;
  config.pin_sccb_sda = PIN_SIOD;
  config.pin_sccb_scl = PIN_SIOC;
  config.pin_pwdn = PIN_PWDN;
  config.pin_reset = PIN_RESET;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = 11;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 14;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }

  if (esp_camera_init(&config) != ESP_OK) {
    return false;
  }

  sensor_t* sensor = esp_camera_sensor_get();
  sensor->set_vflip(sensor, 1);
  sensor->set_hmirror(sensor, 1);
  return true;
}

void applyLed(uint8_t level) {
  ledLevel = level;
  ledcWrite(LEDC_CHANNEL_1, ledLevel);
}

void handleCapture() {
  camera_fb_t* frame = esp_camera_fb_get();
  if (!frame) {
    sendJson(503, "{\"detail\":\"Camera capture failed\"}");
    return;
  }

  WiFiClient client = server.client();
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.setContentLength(frame->len);
  server.send(200, "image/jpeg", "");
  client.write(frame->buf, frame->len);
  esp_camera_fb_return(frame);
}

void handleStatus() {
  sensor_t* sensor = esp_camera_sensor_get();
  const framesize_t frameSize = sensor ? static_cast<framesize_t>(sensor->status.framesize) : FRAMESIZE_INVALID;
  String resolution = "unknown";
  if (frameSize == FRAMESIZE_VGA) resolution = "640x480";
  if (frameSize == FRAMESIZE_SVGA) resolution = "800x600";
  if (frameSize == FRAMESIZE_XGA) resolution = "1024x768";
  if (frameSize == FRAMESIZE_SXGA) resolution = "1280x1024";
  if (frameSize == FRAMESIZE_UXGA) resolution = "1600x1200";

  String body = "{\"online\":true,\"name\":\"" + String(DEVICE_NAME) + "\",\"rssi\":" +
                String(WiFi.RSSI()) + ",\"heap\":" + String(ESP.getFreeHeap()) +
                ",\"uptime_ms\":" + String(millis() - startedAt) + ",\"resolution\":\"" +
                resolution + "\",\"led_level\":" + String(ledLevel) + "}";
  sendJson(200, body);
}

void handleLed() {
  int level = -1;
  if (server.hasArg("level")) {
    level = constrain(server.arg("level").toInt(), 0, 255);
  } else if (server.hasArg("state")) {
    level = server.arg("state") == "on" ? 255 : 0;
  }

  if (level < 0) {
    sendJson(400, "{\"detail\":\"Provide state=on|off or level=0..255\"}");
    return;
  }
  applyLed(static_cast<uint8_t>(level));
  sendJson(200, "{\"led_level\":" + String(ledLevel) + "}");
}

void handleCameraSettings() {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    sendJson(503, "{\"detail\":\"Camera unavailable\"}");
    return;
  }

  if (server.hasArg("quality")) {
    sensor->set_quality(sensor, constrain(server.arg("quality").toInt(), 4, 63));
  }
  if (server.hasArg("framesize")) {
    String value = server.arg("framesize");
    value.toLowerCase();
    if (value == "vga") sensor->set_framesize(sensor, FRAMESIZE_VGA);
    if (value == "svga") sensor->set_framesize(sensor, FRAMESIZE_SVGA);
    if (value == "xga") sensor->set_framesize(sensor, FRAMESIZE_XGA);
    if (value == "sxga") sensor->set_framesize(sensor, FRAMESIZE_SXGA);
    if (value == "uxga") sensor->set_framesize(sensor, FRAMESIZE_UXGA);
  }
  if (server.hasArg("lock_exposure")) {
    const String value = server.arg("lock_exposure");
    sensor->set_exposure_ctrl(sensor, (value == "true" || value == "1") ? 0 : 1);
  }
  sendJson(200, "{\"ok\":true}");
}

void handleSend() {
  if (String(SERVER_URL).length() == 0 || String(DEVICE_API_KEY).length() == 0) {
    sendJson(400, "{\"detail\":\"Configure SERVER_URL and DEVICE_API_KEY in secrets.h\"}");
    return;
  }

  camera_fb_t* frame = esp_camera_fb_get();
  if (!frame) {
    sendJson(503, "{\"detail\":\"Camera capture failed\"}");
    return;
  }

  HTTPClient http;
  const String target = String(SERVER_URL) + "/api/device/upload";
  http.begin(target);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-API-Key", DEVICE_API_KEY);
  if (server.hasArg("sample_id")) {
    http.addHeader("X-Sample-Id", server.arg("sample_id"));
  }
  const int status = http.POST(frame->buf, frame->len);
  const String response = http.getString();
  http.end();
  esp_camera_fb_return(frame);

  if (status < 200 || status >= 300) {
    sendJson(502, "{\"detail\":\"Upload failed\",\"status\":" + String(status) + ",\"response\":" + response + "}");
    return;
  }
  sendJson(200, response);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  const unsigned long deadline = millis() + 30000;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(400);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Camera ready at http://");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("Wi-Fi connection failed; check secrets.h and reboot.");
  }
}

void configureRoutes() {
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/stream-frame", HTTP_GET, handleCapture);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/led", HTTP_GET, handleLed);
  server.on("/led", HTTP_POST, handleLed);
  server.on("/config", HTTP_GET, handleCameraSettings);
  server.on("/send", HTTP_POST, handleSend);
  server.onNotFound([]() { sendJson(404, "{\"detail\":\"Not found\"}"); });
  server.begin();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  startedAt = millis();
  pinMode(PIN_LED, OUTPUT);
  ledcSetup(LEDC_CHANNEL_1, 5000, 8);
  ledcAttachPin(PIN_LED, LEDC_CHANNEL_1);
  applyLed(0);

  if (!initCamera()) {
    Serial.println("Camera initialization failed.");
    return;
  }
  connectWiFi();
  configureRoutes();
}

void loop() {
  server.handleClient();
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(100);
  }
}
