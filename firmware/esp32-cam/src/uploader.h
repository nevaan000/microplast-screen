#pragma once

#include <Arduino.h>

// Push mode: the camera captures a session and uploads it straight to the
// backend, which analyses the frames once the session is marked complete.
namespace uploader {

struct Result {
  bool ok = false;
  int uploaded = 0;
  int requested = 0;
  int status = 0;
  String detail;
};

bool configure(const char* serverUrl, const char* apiKey);
bool configured();

// Captures `frames` frames and POSTs each to <server>/api/device/upload.
// Frames before the last carry X-Capture-Complete: false so the backend stores
// them without analysing; the final frame triggers the analysis.
Result sendSession(int sampleId, int frames);

}  // namespace uploader
