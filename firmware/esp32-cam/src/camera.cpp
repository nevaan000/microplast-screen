#include "camera.h"

namespace {

// AI-Thinker ESP32-CAM OV2640 pin map.
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

// The sensor pipeline needs a couple of frames to settle after init or any
// settings change, otherwise the first captures are dark or half-exposed.
constexpr int WARM_UP_FRAMES = 2;

bool initialized = false;
bool usesPsram = false;
bool locked = false;
int pendingWarmUp = WARM_UP_FRAMES;

void scheduleWarmUp() { pendingWarmUp = WARM_UP_FRAMES; }

}  // namespace

namespace camera {

bool begin() {
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

  usesPsram = psramFound();
  if (usesPsram) {
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    // Without PSRAM there is no room for a UXGA frame buffer.
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
  if (sensor) {
    sensor->set_vflip(sensor, 1);
    sensor->set_hmirror(sensor, 1);
  }

  initialized = true;
  scheduleWarmUp();
  return true;
}

bool ready() { return initialized; }

bool hasPsram() { return usesPsram; }

camera_fb_t* capture() {
  if (!initialized) {
    return nullptr;
  }
  while (pendingWarmUp > 0) {
    --pendingWarmUp;
    camera_fb_t* stale = esp_camera_fb_get();
    if (!stale) {
      return nullptr;
    }
    esp_camera_fb_return(stale);
  }
  return esp_camera_fb_get();
}

void release(camera_fb_t* frame) {
  if (frame) {
    esp_camera_fb_return(frame);
  }
}

bool setFrameSize(const String& name) {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    return false;
  }
  String value = name;
  value.toLowerCase();
  framesize_t size = FRAMESIZE_INVALID;
  if (value == "vga") size = FRAMESIZE_VGA;
  else if (value == "svga") size = FRAMESIZE_SVGA;
  else if (value == "xga") size = FRAMESIZE_XGA;
  else if (value == "sxga") size = FRAMESIZE_SXGA;
  else if (value == "uxga") size = usesPsram ? FRAMESIZE_UXGA : FRAMESIZE_INVALID;
  if (size == FRAMESIZE_INVALID) {
    return false;
  }
  sensor->set_framesize(sensor, size);
  scheduleWarmUp();
  return true;
}

bool setQuality(int quality) {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    return false;
  }
  sensor->set_quality(sensor, constrain(quality, 4, 63));
  scheduleWarmUp();
  return true;
}

bool setExposureLock(bool lock) {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    return false;
  }
  const int automatic = lock ? 0 : 1;
  sensor->set_exposure_ctrl(sensor, automatic);
  sensor->set_aec2(sensor, automatic);
  sensor->set_gain_ctrl(sensor, automatic);
  sensor->set_whitebal(sensor, automatic);
  sensor->set_awb_gain(sensor, automatic);
  locked = lock;
  scheduleWarmUp();
  return true;
}

bool exposureLocked() { return locked; }

int quality() {
  sensor_t* sensor = esp_camera_sensor_get();
  return sensor ? sensor->status.quality : -1;
}

const char* frameSizeName() {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    return "UNKNOWN";
  }
  switch (static_cast<framesize_t>(sensor->status.framesize)) {
    case FRAMESIZE_QVGA: return "QVGA";
    case FRAMESIZE_CIF: return "CIF";
    case FRAMESIZE_VGA: return "VGA";
    case FRAMESIZE_SVGA: return "SVGA";
    case FRAMESIZE_XGA: return "XGA";
    case FRAMESIZE_SXGA: return "SXGA";
    case FRAMESIZE_UXGA: return "UXGA";
    default: return "UNKNOWN";
  }
}

const char* resolution() {
  sensor_t* sensor = esp_camera_sensor_get();
  if (!sensor) {
    return "unknown";
  }
  switch (static_cast<framesize_t>(sensor->status.framesize)) {
    case FRAMESIZE_QVGA: return "320x240";
    case FRAMESIZE_CIF: return "400x296";
    case FRAMESIZE_VGA: return "640x480";
    case FRAMESIZE_SVGA: return "800x600";
    case FRAMESIZE_XGA: return "1024x768";
    case FRAMESIZE_SXGA: return "1280x1024";
    case FRAMESIZE_UXGA: return "1600x1200";
    default: return "unknown";
  }
}

}  // namespace camera
