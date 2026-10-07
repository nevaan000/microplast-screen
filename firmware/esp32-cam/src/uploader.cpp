#include "uploader.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include "camera.h"
#include "esp_system.h"

namespace {

constexpr int MAX_ATTEMPTS = 3;
// The final frame of a session blocks while the backend runs the pipeline.
constexpr uint16_t HTTP_TIMEOUT_MS = 20000;
constexpr unsigned long RETRY_BASE_DELAY_MS = 500;

String serverUrl;
String apiKey;

String makeSessionId() {
  char buffer[16];
  snprintf(buffer, sizeof(buffer), "%08lx%04x", static_cast<unsigned long>(esp_random()),
           static_cast<unsigned>(esp_random() & 0xFFFF));
  return String(buffer);
}

int postFrame(const camera_fb_t* frame, int sampleId, const String& session, bool complete, String& response) {
  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(serverUrl + "/api/device/upload")) {
    response = "Invalid SERVER_URL";
    return -1;
  }
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-API-Key", apiKey);
  http.addHeader("X-Sample-Id", String(sampleId));
  http.addHeader("X-Capture-Session", session);
  http.addHeader("X-Capture-Complete", complete ? "true" : "false");

  const int status = http.POST(frame->buf, frame->len);
  response = status > 0 ? http.getString() : String("Network error: ") + http.errorToString(status);
  http.end();
  return status;
}

}  // namespace

namespace uploader {

bool configure(const char* url, const char* key) {
  serverUrl = url ? String(url) : String();
  serverUrl.trim();
  while (serverUrl.endsWith("/")) {
    serverUrl.remove(serverUrl.length() - 1);
  }
  apiKey = key ? String(key) : String();
  return configured();
}

bool configured() {
  if (serverUrl.length() == 0 || apiKey.length() == 0) {
    return false;
  }
  return serverUrl.startsWith("http://") || serverUrl.startsWith("https://");
}

Result sendSession(int sampleId, int frames) {
  Result result;
  result.requested = frames;
  if (!configured()) {
    result.detail = "Configure SERVER_URL and DEVICE_API_KEY in secrets.h";
    return result;
  }
  if (sampleId <= 0) {
    result.detail = "A positive sample_id is required";
    return result;
  }
  if (!WiFi.isConnected()) {
    result.detail = "Wi-Fi is not connected";
    return result;
  }

  const String session = makeSessionId();
  Serial.printf("[upload] session %s, %d frame(s) for sample %d\n", session.c_str(), frames, sampleId);

  for (int index = 0; index < frames; ++index) {
    const bool last = (index == frames - 1);
    camera_fb_t* frame = camera::capture();
    if (!frame) {
      result.detail = "Camera capture failed";
      return result;
    }

    String response;
    int status = 0;
    for (int attempt = 1; attempt <= MAX_ATTEMPTS; ++attempt) {
      status = postFrame(frame, sampleId, session, last, response);
      if (status >= 200 && status < 300) {
        break;
      }
      // A rejected frame will be rejected again, so only retry transport errors.
      if (status >= 400 && status < 500) {
        break;
      }
      if (attempt < MAX_ATTEMPTS) {
        const unsigned long pause = RETRY_BASE_DELAY_MS << (attempt - 1);
        Serial.printf("[upload] frame %d failed (status %d), retrying in %lu ms\n", index + 1, status, pause);
        delay(pause);
      }
    }
    camera::release(frame);

    if (status < 200 || status >= 300) {
      result.status = status;
      result.detail = response;
      return result;
    }
    result.uploaded = index + 1;
    if (last) {
      result.ok = true;
      result.detail = response;
    }
  }
  return result;
}

}  // namespace uploader
