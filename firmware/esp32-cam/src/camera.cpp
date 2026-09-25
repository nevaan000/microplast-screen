#include "camera.h"

namespace {
constexpr int PWDN = 32, RESET = -1, XCLK = 0, SIOD = 26, SIOC = 27;
constexpr int Y9 = 35, Y8 = 34, Y7 = 39, Y6 = 36, Y5 = 21, Y4 = 19, Y3 = 18, Y2 = 5;
constexpr int VSYNC = 25, HREF = 23, PCLK = 22;
bool exposureLocked = false;

framesize_t parseFrameSize(String value) {
  value.toLowerCase();
  if (value == "vga") return FRAMESIZE_VGA;
  if (value == "svga") return FRAMESIZE_SVGA;
  if (value == "xga") return FRAMESIZE_XGA;
  if (value == "sxga") return FRAMESIZE_SXGA;
  return FRAMESIZE_UXGA;
}

const char* frameSizeName(framesize_t value) {
  switch (value) {
    case FRAMESIZE_VGA: return "VGA";
    case FRAMESIZE_SVGA: return "SVGA";
    case FRAMESIZE_XGA: return "XGA";
    case FRAMESIZE_SXGA: return "SXGA";
    case FRAMESIZE_UXGA: return "UXGA";
    default: return "unknown";
  }
}
}

bool cameraBegin() {
  camera_config_t config{};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2; config.pin_d1 = Y3; config.pin_d2 = Y4; config.pin_d3 = Y5;
  config.pin_d4 = Y6; config.pin_d5 = Y7; config.pin_d6 = Y8; config.pin_d7 = Y9;
  config.pin_xclk = XCLK; config.pin_pclk = PCLK; config.pin_vsync = VSYNC; config.pin_href = HREF;
  config.pin_sccb_sda = SIOD; config.pin_sccb_scl = SIOC; config.pin_pwdn = PWDN; config.pin_reset = RESET;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = psramFound() ? FRAMESIZE_UXGA : FRAMESIZE_VGA;
  config.jpeg_quality = psramFound() ? 10 : 14;
  config.fb_count = psramFound() ? 2 : 1;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;
  if (esp_camera_init(&config) != ESP_OK) return false;

  sensor_t* sensor = esp_camera_sensor_get();
  sensor->set_vflip(sensor, 1);
  sensor->set_hmirror(sensor, 1);
  for (int i = 0; i < 2; ++i) {
    camera_fb_t* frame = esp_camera_fb_get();
    if (frame) esp_camera_fb_return(frame);
  }
  return true;
}

camera_fb_t* cameraCapture() { return esp_camera_fb_get(); }
void cameraRelease(camera_fb_t* frame) { if (frame) esp_camera_fb_return(frame); }

bool cameraConfigure(const String& frameSize, int quality, bool lockExposure) {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) return false;
  if (frameSize.length()) sensor->set_framesize(sensor, parseFrameSize(frameSize));
  if (quality >= 4 && quality <= 63) sensor->set_quality(sensor, quality);
  sensor->set_exposure_ctrl(sensor, lockExposure ? 0 : 1);
  sensor->set_gain_ctrl(sensor, lockExposure ? 0 : 1);
  sensor->set_whitebal(sensor, lockExposure ? 0 : 1);
  exposureLocked = lockExposure;
  for (int i = 0; i < 2; ++i) {
    camera_fb_t* frame = esp_camera_fb_get();
    if (frame) esp_camera_fb_return(frame);
  }
  return true;
}

String cameraStatusJson() {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) return "\"framesize\":\"unknown\",\"quality\":0,\"exposure_locked\":false";
  return String("\"framesize\":\"") + frameSizeName(static_cast<framesize_t>(sensor->status.framesize)) +
         "\",\"quality\":" + String(sensor->status.quality) +
         ",\"exposure_locked\":" + (exposureLocked ? "true" : "false");
}
