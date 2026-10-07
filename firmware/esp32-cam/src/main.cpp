#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>
#include "esp_system.h"

#include "camera.h"
#include "led.h"
#include "uploader.h"
#include "network.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID ""
#define WIFI_PASS ""
#define DEVICE_NAME "microplast-cam"
#define SERVER_URL ""
#define DEVICE_API_KEY ""
#endif

// Chamber illumination and the physical capture trigger. Both pins are only
// free when no microSD card is fitted, because the card slot uses GPIO 12-15.
//
// GPIO 13 is safe for the external LED driver: it is not a strapping pin.
// GPIO 12 (MTDI) IS a strapping pin - driving it high at reset selects 1.8 V
// flash and the board will not boot. It is therefore used for the button with
// an internal pull-DOWN, so the pin idles low and a press connects it to 3V3.
// Wire the button between GPIO 12 and 3V3, never to a pull-up.
#ifndef EXTERNAL_LED_PIN
#define EXTERNAL_LED_PIN 13
#endif
#ifndef CAPTURE_BUTTON_PIN
#define CAPTURE_BUTTON_PIN 12
#endif
#ifndef CAPTURE_BUTTON_FRAMES
#define CAPTURE_BUTTON_FRAMES 3
#endif

namespace {

constexpr int PIN_ONBOARD_LED = 4;
constexpr unsigned long BUTTON_DEBOUNCE_MS = 250;

WebServer server(80);
uint32_t startedAt = 0;
bool buttonEnabled = false;
bool buttonState = false;
bool sessionFired = false;
unsigned long buttonChangedAt = 0;
// The physical button replays the most recent push session's sample.
int lastSampleId = 0;

const char INDEX_PAGE[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MicroPlast CAM</title>
<style>
body{font:14px system-ui,sans-serif;margin:1rem;background:#0b1220;color:#e2e8f0}
h1{font-size:1.2rem}img{max-width:100%;border-radius:8px;background:#000}
.row{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin:.8rem 0}
button{padding:.5rem .9rem;border:0;border-radius:6px;background:#0ea5e9;color:#fff;font:inherit;cursor:pointer}
button.off{background:#475569}input[type=range]{width:180px}
code,p{color:#94a3b8}
</style></head><body>
<h1>MicroPlast CAM</h1>
<p id="info">Reading status&hellip;</p>
<img id="view" alt="Live capture">
<div class="row">
<label>LED <input id="level" type="range" min="0" max="255" value="0"></label>
<span id="out">0</span>
<button id="apply">Apply</button>
<button id="dark" class="off">Off</button>
<button id="frame">Refresh frame</button>
</div>
<p>This page is for bench testing only. Use the MicroPlast Screen dashboard for
calibration, capture sessions, and analysis.</p>
<script>
const $ = id => document.getElementById(id);
async function status() {
  try {
    const info = await (await fetch('/status')).json();
    $('info').textContent = info.ip + ' - ' + info.framesize + ' ' + info.resolution +
      ', quality ' + info.quality + ', LED ' + info.led_level +
      ', exposure ' + (info.exposure_locked ? 'locked' : 'auto') +
      ', RSSI ' + info.rssi + ' dBm, free heap ' + info.free_heap +
      ', PSRAM ' + (info.psram ? 'yes' : 'no') + ', uptime ' + info.uptime_s + ' s';
  } catch (error) { $('info').textContent = 'Status unavailable: ' + error; }
}
function frame() { $('view').src = '/capture?t=' + Date.now(); status(); }
async function led(level) {
  try { await fetch('/led?level=' + level); } catch (error) { /* status refresh reports the failure */ }
  status();
}
$('level').oninput = e => { $('out').textContent = e.target.value; };
$('apply').onclick = () => led($('level').value);
$('dark').onclick = () => { $('level').value = 0; $('out').textContent = '0'; led(0); };
$('frame').onclick = frame;
frame();
setInterval(status, 5000);
</script></body></html>
)HTML";

void sendJson(int status, const String& body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(status, "application/json", body);
}

void sendError(int status, const String& detail) {
  sendJson(status, "{\"detail\":\"" + detail + "\"}");
}

// Backend error bodies are JSON text, so quote and control characters must be
// escaped before they are embedded in another JSON string.
String escapeJson(const String& value) {
  String out;
  out.reserve(value.length() + 8);
  for (const char character : value) {
    switch (character) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if (static_cast<unsigned char>(character) < 0x20) {
          char buffer[7];
          snprintf(buffer, sizeof(buffer), "\\u%04x", static_cast<unsigned char>(character));
          out += buffer;
        } else {
          out += character;
        }
    }
  }
  return out;
}

void handleIndex() { server.send_P(200, "text/html", INDEX_PAGE); }

void handleCapture() {
  if (!camera::ready()) {
    sendError(503, "Camera unavailable");
    return;
  }
  camera_fb_t* frame = camera::capture();
  if (!frame) {
    sendError(503, "Camera capture failed");
    return;
  }
  WiFiClient client = server.client();
  server.sendHeader("Cache-Control", "no-store");
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.setContentLength(frame->len);
  server.send(200, "image/jpeg", "");
  client.write(frame->buf, frame->len);
  camera::release(frame);
}

void handleStatus() {
  String body = "{";
  body += "\"online\":true,";
  body += "\"name\":\"" + String(DEVICE_NAME) + "\",";
  body += "\"ip\":\"" + network::address() + "\",";
  body += "\"rssi\":" + String(network::rssi()) + ",";
  body += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
  body += "\"psram\":" + String(camera::hasPsram() ? "true" : "false") + ",";
  body += "\"framesize\":\"" + String(camera::frameSizeName()) + "\",";
  body += "\"resolution\":\"" + String(camera::resolution()) + "\",";
  body += "\"quality\":" + String(camera::quality()) + ",";
  body += "\"led_level\":" + String(led::level()) + ",";
  body += "\"external_led\":" + String(led::externalAttached() ? "true" : "false") + ",";
  body += "\"exposure_locked\":" + String(camera::exposureLocked() ? "true" : "false") + ",";
  body += "\"uptime_s\":" + String((millis() - startedAt) / 1000);
  body += "}";
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
    sendError(400, "Provide state=on|off or level=0..255");
    return;
  }
  led::setLevel(static_cast<uint8_t>(level));
  sendJson(200, "{\"led_level\":" + String(led::level()) + "}");
}

void handleConfig() {
  if (!camera::ready()) {
    sendError(503, "Camera unavailable");
    return;
  }
  bool changed = false;
  if (server.hasArg("quality")) {
    changed = camera::setQuality(server.arg("quality").toInt()) || changed;
  }
  if (server.hasArg("framesize")) {
    if (!camera::setFrameSize(server.arg("framesize"))) {
      sendError(422, "Unsupported framesize, or UXGA requested without PSRAM");
      return;
    }
    changed = true;
  }
  if (server.hasArg("lock_exposure")) {
    // httpx serialises Python booleans as "True"/"False", so compare lowercased.
    String value = server.arg("lock_exposure");
    value.toLowerCase();
    changed = camera::setExposureLock(value == "true" || value == "1" || value == "on") || changed;
  }
  if (!changed) {
    sendError(422, "Provide framesize, quality, or lock_exposure");
    return;
  }
  sendJson(200, "{\"ok\":true,\"framesize\":\"" + String(camera::frameSizeName()) +
                    "\",\"quality\":" + String(camera::quality()) +
                    ",\"exposure_locked\":" + String(camera::exposureLocked() ? "true" : "false") + "}");
}

void handleCaptureAndSend() {
  if (!uploader::configured()) {
    sendError(400, "Configure SERVER_URL and DEVICE_API_KEY in secrets.h");
    return;
  }
  const int sampleId = server.hasArg("sample_id") ? server.arg("sample_id").toInt() : 0;
  const int frames = server.hasArg("frames") ? constrain(server.arg("frames").toInt(), 1, 10) : 1;
  if (sampleId <= 0) {
    sendError(422, "Provide sample_id of an existing MicroPlast Screen sample");
    return;
  }
  lastSampleId = sampleId;

  const uploader::Result result = uploader::sendSession(sampleId, frames);
  if (!result.ok) {
    String body = "{\"detail\":\"" + escapeJson(result.detail) + "\",\"status\":" + String(result.status) +
                  ",\"uploaded\":" + String(result.uploaded) + ",\"requested\":" + String(result.requested) + "}";
    sendJson(502, body);
    return;
  }
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", result.detail);
}

void configureRoutes() {
  server.on("/", HTTP_GET, handleIndex);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/led", HTTP_GET, handleLed);
  server.on("/led", HTTP_POST, handleLed);
  server.on("/config", HTTP_GET, handleConfig);
  server.on("/config", HTTP_POST, handleConfig);
  server.on("/capture-and-send", HTTP_POST, handleCaptureAndSend);
  server.onNotFound([]() { sendError(404, "Not found"); });
  server.begin();
}

void pollButton() {
  if (!buttonEnabled) {
    return;
  }
  const bool reading = digitalRead(CAPTURE_BUTTON_PIN) == HIGH;
  const unsigned long now = millis();
  if (reading != buttonState) {
    buttonState = reading;
    buttonChangedAt = now;
    if (!buttonState) {
      sessionFired = false;
    }
    return;
  }
  if (!buttonState || sessionFired || now - buttonChangedAt < BUTTON_DEBOUNCE_MS) {
    return;
  }
  sessionFired = true;

  if (lastSampleId <= 0) {
    Serial.println("[button] no sample_id yet; POST /capture-and-send?sample_id=N&frames=M first.");
    return;
  }
  Serial.printf("[button] capturing %d frame(s) for sample %d\n", CAPTURE_BUTTON_FRAMES, lastSampleId);
  const uploader::Result result = uploader::sendSession(lastSampleId, CAPTURE_BUTTON_FRAMES);
  Serial.printf("[button] %s: %d/%d uploaded %s\n", result.ok ? "ok" : "failed", result.uploaded, result.requested,
                result.detail.c_str());
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  startedAt = millis();
  Serial.println();
  Serial.println("MicroPlast Screen ESP32-CAM firmware");

  led::begin(PIN_ONBOARD_LED, EXTERNAL_LED_PIN);

  if (!camera::begin()) {
    Serial.println("Camera initialization failed. Check the ribbon connector and the 5 V supply.");
    // Keep Wi-Fi and the status endpoint alive so the failure is visible remotely.
  }

  network::begin(WIFI_SSID, WIFI_PASS, DEVICE_NAME);
  uploader::configure(SERVER_URL, DEVICE_API_KEY);
  Serial.printf("Push mode: %s\n", uploader::configured() ? "configured" : "SERVER_URL or DEVICE_API_KEY missing");

  pinMode(CAPTURE_BUTTON_PIN, INPUT_PULLDOWN);
  buttonEnabled = uploader::configured();
  buttonState = digitalRead(CAPTURE_BUTTON_PIN) == HIGH;
  buttonChangedAt = millis();

  configureRoutes();
  Serial.printf("HTTP server listening on port 80. Try http://%s.local/\n", network::hostname());
}

void loop() {
  server.handleClient();
  network::maintain();
  pollButton();
}
