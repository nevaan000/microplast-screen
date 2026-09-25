# MicroPlast Screen

MicroPlast Screen is a local visual-screening application for filter images from uploads, synthetic demos, or an ESP32-CAM. It uses OpenCV contour analysis and an optional local classifier to identify particles that **visually resemble microplastics**.

> **Scientific limitation:** This is a low-cost optical screening result, not laboratory-grade chemical or polymer identification. Confirm suspected microplastics with FTIR or Raman spectroscopy before making scientific, regulatory, or health decisions.

## Requirements

- Python 3.10 or newer
- A current desktop browser
- An ESP32-CAM and a USB-to-UART adapter only for camera capture
- PlatformIO only for firmware builds and flashing

No Node.js installation is required. The backend serves the static frontend and stores data locally in SQLite.

## Start the application

Run these commands from the project root.

### Windows

```bat
run.bat
```

### macOS and Linux

```sh
./run.sh
```

Each script creates `.venv`, installs `requirements.txt`, and starts the application at `http://127.0.0.1:8000`. Open that address in a browser.

To run manually on any platform:

```sh
python -m venv .venv
```

Activate the environment:

```bat
.venv\Scripts\activate
```

```sh
. .venv/bin/activate
```

Then install and run:

```sh
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The API documentation is available at `http://127.0.0.1:8000/docs` while the server is running.

## Local and LAN security

This dashboard is for **local or trusted-LAN operation only. Do not expose it to the public internet.** The ESP32-CAM control and image traffic use HTTP, and the browser stores the device API key in local storage.

For trusted-LAN access on macOS or Linux, bind the runner explicitly:

```sh
HOST=0.0.0.0 PORT=8000 ./run.sh
```

On Windows, start Uvicorn manually after `run.bat` has created the environment:

```bat
.venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Allow access only from the trusted local network in the host firewall. Do not configure router port forwarding, a public DNS record, or a public reverse proxy for this application.

## Configuration

Copy the environment template before configuring an ESP32-CAM or changing defaults:

```bat
copy .env.example .env
```

```sh
cp .env.example .env
```

Generate a device key locally, then place it in `DEVICE_API_KEY` in `.env`:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Change the example key; it is intentionally public and unsuitable for use. Keep `.env` and `firmware/esp32-cam/include/secrets.h` private and untracked.

Important `.env` values:

- `DEVICE_API_KEY`: shared credential for device-control and device-upload requests.
- `ESP32_IP`: camera hostname or IP address, optionally with a port; do not include `http://`.
- `MAX_UPLOAD_MB`: maximum accepted upload size.
- `DATA_DIR`: local storage root, defaulting to `data`.

The application stores its SQLite database at `data/microplastic.db`. Uploaded originals, annotated images, and masks are stored in `data/raw`, `data/processed`, and `data/masks`. Delete samples through the History page so database records and generated assets are removed together.

## Screening workflows

### Upload filter images

1. Select **New analysis** → **Upload images**.
2. Choose one or more JPEG or PNG images of the same filter and dimensions.
3. Enter sample details, including sampled water volume when known.
4. Select **Analyse images**.

Multiple image frames are median-stacked before processing, which helps suppress sensor noise. The result page includes the original, annotated image, mask, measurements, charts, particle-class corrections, and CSV, JSON, and PDF exports.

### Synthetic demo

1. Select **New analysis** → **Demo (synthetic)**.
2. Set particle count, fibre ratio, sensor noise, and lighting gradient.
3. Select **Generate & analyse**.

Use this workflow to explore controls and verify the installation. It creates a normal local sample, so delete demo results from History when they are no longer needed.

### Calibration

Physical measurements require an active calibration. Without one, dimensions are reported in pixels and concentrations remain optical estimates.

1. Capture a ruler or stage-micrometer image at the same camera distance, focus, resolution, and filter position used for samples.
2. Open **Calibration** and upload the image.
3. Select the two endpoints of a known reference.
4. Enter the real reference distance in millimetres and save.

The application calculates millimetres per pixel from the selected distance. A newly saved calibration becomes active and replaces the previous active calibration. Recalibrate whenever camera distance, focus, resolution, lens configuration, or sample position changes.

### ESP32-CAM capture

1. Configure and flash the camera firmware as described below.
2. Set the device host in `.env` or in **Settings**.
3. Open **Device**, enter the shared device API key in the browser, and test the live preview.
4. Open **New analysis** → **Capture from ESP32-CAM**.
5. Choose the number of frames and LED level, then select **Capture & analyse**.

The app first verifies that a device key is configured. It then creates the sample, optionally enables the chamber LED, captures frames through the backend, and switches the LED off after capture.

## ESP32-CAM firmware

The firmware project is in `firmware/esp32-cam` and targets the AI Thinker ESP32-CAM board.

Install PlatformIO into the active Python environment:

```sh
python -m pip install platformio
```

Create the private firmware credentials file:

```bat
copy firmware\esp32-cam\include\secrets.h.example firmware\esp32-cam\include\secrets.h
```

```sh
cp firmware/esp32-cam/include/secrets.h.example firmware/esp32-cam/include/secrets.h
```

Set `WIFI_SSID`, `WIFI_PASSWORD`, `DEVICE_NAME`, `SERVER_URL`, and `DEVICE_API_KEY` in `secrets.h`. `SERVER_URL` must be the LAN address of the computer running this backend, including its port, such as `http://192.168.1.50:8000`. The firmware and backend `DEVICE_API_KEY` values must match exactly.

Build the firmware:

```sh
python -m platformio run --project-dir firmware/esp32-cam
```

To flash an AI Thinker ESP32-CAM with a USB-to-UART adapter:

1. Power the board from a stable 5 V supply.
2. Connect adapter ground to board ground, adapter TX to U0R, and adapter RX to U0T.
3. Connect GPIO 0 to ground, reset or power-cycle the board, then leave GPIO 0 grounded for upload mode.
4. Run the upload command:

   ```sh
   python -m platformio run --project-dir firmware/esp32-cam --target upload
   ```

5. Disconnect GPIO 0 from ground and reset or power-cycle the board to start the camera firmware.
6. Monitor serial output at 115200 baud:

   ```sh
   python -m platformio device monitor --project-dir firmware/esp32-cam --baud 115200
   ```

PlatformIO normally detects the connected serial adapter. If it cannot, identify the adapter with `python -m platformio device list`, then set the correct upload port in PlatformIO for that connected board before retrying. The camera and server must use the same trusted LAN.

## Processing assumptions and limitations

- Images should show a flat filter under consistent, diffuse illumination and stable focus.
- The system identifies visible particles by geometry, colour, texture, and configured visual rules. It cannot determine polymer chemistry.
- Dust, organic material, mineral grains, air bubbles, filter texture, and filter damage can cause false positives.
- Transparent, overlapping, very small, blurred, or poorly illuminated particles may be missed or measured unreliably.
- Distance, focus, resolution, compression, and lighting changes affect segmentation and measurement. Use calibration and repeatable capture conditions.
- Classifier results depend on its local training data and verified labels; they are not independent laboratory validation.
- Use the results for triage and optical estimation, not as a replacement for laboratory quality assurance.

## Settings and review

- **Settings** controls segmentation thresholds, size and shape rules, circular region-of-interest settings, and device parameters.
- **History** filters, compares, exports, and deletes local samples.
- **ML lab** shows classifier status and uses verified particle-class corrections as local training labels.
- **Method & limitations** presents the scientific and operational limits in the interface.

## Tests

Run the backend test suite from the project root:

```sh
python -m pytest backend/tests
```

The test suite covers the image pipeline, circular ROI handling, calibration behavior, API upload/export/delete flow, and device-upload authentication.
