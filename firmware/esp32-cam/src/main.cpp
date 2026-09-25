#include <Arduino.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include "esp_system.h"

#include "camera.h"
#include "led.h"
#include "wifi.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define DEVICE_NAME "microplast-cam"
#define SERVER_URL ""
#define DEVICE_API_KEY ""
#endif

namespace {
WebServer server(80);
uint32_t startedAt = 0;

void sendJson(int status, const String& body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(status, "application/json", body);
}

bool truthy(const String& value) {
  return value == "1" || value == "true" || value == "on";
}

void handleCapture() {
  camera_fb_t* frame = cameraCapture();
  if (!frame) {
    sendJson(503, "{\"detail\":\"Camera capture failed\"}");
    return;
  }
  WiFiClient client = server.client();
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.setContentLength(frame->len);
  server.send(200, "image/jpeg", "");
  client.write(frame->buf, frame->len);
  cameraRelease(frame);
}

void handleStatus() {
  String body = String("{\"uptime_s\":") + String((millis() - startedAt) / 1000) +
                ",\"rssi\":" + String(WiFi.RSSI()) +
                ",\"free_heap\":" + String(ESP.getFreeHeap()) +
                ",\"psram\":" + (psramFound() ? "true" : "false") +
                ",\"led_level\":" + String(ledLevel()) +
                ",\"ip\":\"" + wifiIp() + "\"," + cameraStatusJson() + "}";
  sendJson(200, body);
}

void handleLed() {
  int level = -1;
  if (server.hasArg("level")) level = constrain(server.arg("level").toInt(), 0, 255);
  else if (server.hasArg("state")) level = server.arg("state") == "on" ? 255 : 0;
  if (level < 0) {
    sendJson(400, "{\"detail\":\"Provide state=on|off or level=0..255\"}");
    return;
  }
  ledSet(static_cast<uint8_t>(level));
  sendJson(200, String("{\"led_level\":") + String(ledLevel()) + "}");
}

void handleConfig() {
  const String frameSize = server.hasArg("framesize") ? server.arg("framesize") : "";
  const int quality = server.hasArg("quality") ? constrain(server.arg("quality").toInt(), 4, 63) : -1;
  const bool lockExposure = server.hasArg("lock_exposure") && truthy(server.arg("lock_exposure"));
  if (!frameSize.length() && quality < 0 && !server.hasArg("lock_exposure")) {
    sendJson(400, "{\"detail\":\"Provide framesize, quality, or lock_exposure\"}");
    return;
  }
  if (!cameraConfigure(frameSize, quality, lockExposure)) {
    sendJson(503, "{\"detail\":\"Camera unavailable\"}");
    return;
  }
  sendJson(200, String("{\"ok\":true,") + cameraStatusJson() + "}");
}

bool sendFrame(camera_fb_t* frame, const String& session, int sampleId, bool complete, String& responseBody) {
  HTTPClient http;
  if (!http.begin(String(SERVER_URL) + "/api/device/upload")) return false;
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-API-Key", DEVICE_API_KEY);
  http.addHeader("X-Sample-Id", String(sampleId));
  http.addHeader("X-Capture-Session", session);
  http.addHeader("X-Capture-Complete", complete ? "true" : "false");
  const int status = http.POST(frame->buf, frame->len);
  responseBody = http.getString();
  http.end();
  return status >= 200 && status < 300;
}

void handleCaptureAndSend() {
  if (!String(SERVER_URL).length() || !String(DEVICE_API_KEY).length()) {
    sendJson(400, "{\"detail\":\"Configure SERVER_URL and DEVICE_API_KEY in secrets.h\"}");
    return;
  }
  if (!server.hasArg("sample_id")) {
    sendJson(400, "{\"detail\":\"sample_id is required\"}");
    return;
  }
  const int sampleId = server.arg("sample_id").toInt();
  const int frames = constrain(server.hasArg("frames") ? server.arg("frames").toInt() : 1, 1, 10);
  const String session = String(millis(), HEX) + String(random(0xFFFF), HEX);
  String lastResponse;
  for (int index = 0; index < frames; ++index) {
    camera_fb_t* frame = cameraCapture();
    if (!frame) {
      sendJson(503, "{\"detail\":\"Camera capture failed\"}");
      return;
    }
    const bool ok = sendFrame(frame, session, sampleId, index == frames - 1, lastResponse);
    cameraRelease(frame);
    if (!ok) {
      sendJson(502, String("{\"detail\":\"Upload failed on frame \") + String(index + 1) + "\"}");
      return;
    }
  }
  sendJson(200, lastResponse.length() ? lastResponse : "{\"ok\":true}");
}

void handleIndex() {
  const char page[] PROGMEM = R"HTML(
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroPlast CAM</title>
<style>body{font:16px system-ui;margin:2rem;max-width:720px;background:#081b24;color:#e7f9fb}img{max-width:100%;border-radius:8px}button,input{padding:.6rem;margin:.2rem}#status{color:#7be0c3}</style></head>
<body><h1>MicroPlast CAM</h1><p id="status">Loading…</p><img id="frame" alt="Live camera frame"><p><button onclick="led(255)">LED on</button><button onclick="led(0)">LED off</button><input id="brightness" type="range" min="0" max="255" value="0" oninput="led(this.value)"></p>
<script>const f=document.querySelector('#frame'),s=document.querySelector('#status');async function led(level){await fetch('/led?level='+level)}async function refresh(){f.src='/capture?t='+Date.now();try{const j=await (await fetch('/status')).json();s.textContent=j.ip+' · RSSI '+j.rssi+' · '+j.framesize+' · LED '+j.led_level}catch(e){s.textContent='Status unavailable'}}setInterval(refresh,1000);refresh()</script></body></html>
)HTML";
  server.send(200, "text/html", page);
}

void configureRoutes() {
  server.on("/", HTTP_GET, handleIndex);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/led", HTTP_GET, handleLed);
  server.on("/config", HTTP_GET, handleConfig);
  server.on("/capture-and-send", HTTP_POST, handleCaptureAndSend);
  server.on("/send", HTTP_POST, handleCaptureAndSend);
  server.onNotFound([]() { sendJson(404, "{\"detail\":\"Not found\"}"); });
  server.begin();
}
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  startedAt = millis();
  ledBegin();
  if (!cameraBegin()) {
    Serial.println("Camera initialization failed.");
    return;
  }
  wifiBegin();
  configureRoutes();
}

void loop() {
  server.handleClient();
  wifiMaintain();
}
