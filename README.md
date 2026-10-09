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

## Security model

By default the dashboard assumes **local or trusted-LAN operation with no login**. The ESP32-CAM control and image traffic use HTTP, and the browser stores the device API key in local storage. In that mode, allow access only from the trusted local network in the host firewall, and do not configure router port forwarding, a public DNS record, or a public reverse proxy.

To publish the dashboard, set `ADMIN_PASSWORD` (and optionally `ADMIN_USER`). Every API endpoint except health, sign-in, and device upload then requires a session cookie issued by the sign-in page. Sessions last `SESSION_HOURS` (default 12), are stored in the database, and the cookie is `HttpOnly`, `SameSite=Lax`, and marked `Secure` whenever the request arrives over HTTPS or with `X-Forwarded-Proto: https`. Failed sign-ins are rate-limited per client address. A public deployment must terminate TLS at the host or reverse proxy so credentials and session cookies never travel in clear text.

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
- `ADMIN_USER` / `ADMIN_PASSWORD`: dashboard login. Leave the password empty for local use without a login; set it before publishing.
- `SESSION_HOURS`: how long a sign-in session stays valid, default 12.

The application stores its SQLite database at `data/microplastic.db`. Uploaded originals, annotated images, and masks are stored in `data/raw`, `data/processed`, and `data/masks`. Delete samples through the History page so database records and generated assets are removed together.

## Publishing on a container host

The backend serves the dashboard itself, so a single container provides one public URL for both the UI and the API. A static host such as Vercel is not needed for the frontend and cannot run the backend at all: OpenCV analysis and the SQLite database need a persistent disk and more request time than serverless functions allow.

Build and run the image locally:

```sh
docker build -t microplast-screen .
docker run --rm -p 8000:8000 -v microplast-data:/data -e ADMIN_PASSWORD=pick-a-long-password -e DEVICE_API_KEY=pick-a-device-key microplast-screen
```

The database and generated images live in the `/data` volume; without a volume they disappear when the container is replaced.

On Render, Railway, or Fly.io, deploy this repository as a Docker service, attach a persistent disk mounted at `/data` (Fly.io `fly.toml`: `mounts: source=microplast_data, destination=/data`; Render: add a disk at `/data`; Railway: add a volume with mount path `/data`), set `ADMIN_PASSWORD` and `DEVICE_API_KEY` as environment variables, and let the platform terminate HTTPS. Set `PORT` only if the platform requires a specific value; the image honours it.

Point the ESP32-CAM at the public address by setting `SERVER_URL` in `firmware/esp32-cam/include/secrets.h` to the HTTPS URL, for example `https://microplast-screen.onrender.com`. The firmware uploads over HTTPS and authenticates with `DEVICE_API_KEY`, exactly as on the LAN.

Never publish an instance without `ADMIN_PASSWORD`: anyone who learns the URL could read, upload, and delete samples.

### Optional: serve the dashboard from Vercel

Vercel cannot run the Python backend, but it can host the static dashboard and proxy the API to your container host, giving you one public Vercel URL for everything. `vercel.json` already contains the routing: `/api/*`, `/docs`, and `/openapi.json` are rewritten to an external origin, and every other path is served from `frontend/`.

1. Replace the four `https://YOUR-BACKEND-HOST.example.com` destinations in `vercel.json` with your container host's HTTPS URL. The placeholder is deliberately invalid so a forgotten edit fails loudly instead of proxying to the wrong host.
2. In the Vercel dashboard, import this repository as an **Other** project with no build command and no output directory, then deploy.
3. Keep `ADMIN_PASSWORD` and `DEVICE_API_KEY` set on the container host; Vercel needs no secrets of its own.

Because the proxy keeps the browser on a single origin, the session cookie and the device upload flow work exactly as they do when the backend serves the dashboard itself. API responses are never cached by Vercel's CDN (`x-vercel-enable-rewrite-caching: 0`), so sample lists and results always come from the backend. The ESP32-CAM can post to either URL; both authenticate with `DEVICE_API_KEY`.

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

Set `WIFI_SSID`, `WIFI_PASS`, `DEVICE_NAME`, `SERVER_URL`, and `DEVICE_API_KEY` in `secrets.h`. `SERVER_URL` must be the LAN address of the computer running this backend, including its port, such as `http://192.168.1.50:8000`. The firmware and backend `DEVICE_API_KEY` values must match exactly.

The firmware registers `DEVICE_NAME` over mDNS, so the camera is also reachable at `http://microplast-cam.local/` when the network allows mDNS. Opening that address in a browser shows a bench-test page with a live frame and LED controls.

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

### Firmware endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Bench-test page with a live frame and LED controls. |
| GET | `/capture` | One JPEG frame. |
| GET | `/status` | `uptime_s`, `rssi`, `free_heap`, `psram`, `framesize`, `quality`, `led_level`, `ip`, `exposure_locked`. |
| GET/POST | `/led?state=on\|off&level=0-255` | Chamber illumination level. |
| GET/POST | `/config?framesize=..&quality=..&lock_exposure=0\|1` | Camera settings; `lock_exposure=1` freezes aec, agc, and awb for consistent lighting. |
| POST | `/capture-and-send?sample_id=N&frames=1-10` | Push mode: captures a session and POSTs each frame to the backend `/api/device/upload` with `X-API-Key`, `X-Sample-Id`, and `X-Capture-Session`. Only the final frame carries `X-Capture-Complete: true`, which is what triggers analysis. |

After a successful `/capture-and-send`, pressing the wired capture button replays the same sample for `CAPTURE_BUTTON_FRAMES` frames. The first two frames after boot or any settings change are discarded so the sensor settles before an image is used.

### Wiring

USB-to-UART programming, with the GPIO 0 jumper that forces flash mode:

```text
  USB-to-UART adapter            AI-Thinker ESP32-CAM
  -------------------            --------------------
        GND  --------------------  GND
        TX   --------------------  U0R
        RX   --------------------  U0T
        5 V  ----(optional)------  5 V     (see the power advice below)
                                   GPIO0 --[ jumper ]-- GND   flashing only
```

Remove the GPIO 0 jumper and reset the board after uploading. Never power the board from the adapter's 3.3 V pin.

External LED driver, low-side switched by a logic-level N-channel MOSFET such as an IRLZ44N or AO3400. `EXTERNAL_LED_PIN` defaults to GPIO 13:

```text
            +5 V (external supply, common ground with the ESP32)
              |
            [ LED string with series current-limiting resistor ]
              |
   D ---------+   Drain
   G ----[220R]---- GPIO13
   S ---------+   Source
              |
             GND ---- ESP32 GND
              |
           [10k]  gate-to-ground pulldown, keeps the LED off during boot
              |
             GND
```

Capture button on GPIO 12. GPIO 12 is the MTDI strapping pin: if it is high at reset the board tries to boot with 1.8 V flash and fails. The firmware therefore configures it as `INPUT_PULLDOWN`, so the pin idles low and a press connects it to 3 V 3. Do not use a pull-up on this pin.

```text
   3V3 ----[ momentary button ]---- GPIO12   (internal pull-down, idles low)
```

Override the pins with `-DEXTERNAL_LED_PIN=..` and `-DCAPTURE_BUTTON_PIN=..` build flags, or set `EXTERNAL_LED_PIN` to `-1` to drive only the on-board flash LED. Both pins are unavailable when a microSD card is fitted, because the card slot occupies GPIO 12 to 15.

### Power and brownouts

The ESP32-CAM draws short current peaks above 300 mA when the Wi-Fi radio transmits, and more again when the flash LED is on. Powering it from a USB port, a long thin jumper lead, or a shared breadboard rail causes the brownout detector to reset the board mid-capture.

- Use a regulated **5 V, 2 A minimum** supply with short, thick leads soldered or clamped directly to the 5 V and GND pins.
- Add a **470 µF to 1000 µF electrolytic** plus a **100 nF ceramic** capacitor across the 5 V and GND rails close to the board.
- Keep the external LED string on its own supply rail; do not run it from the ESP32's 3.3 V pin.
- Symptom of an inadequate supply: repeated `Brownout detector was triggered` resets, Wi-Fi dropouts exactly when the LED turns on, or corrupt JPEG frames.

### Camera mounting

- Fix the board to a rigid bracket so the lens stays square to the filter and the distance cannot drift. Any movement invalidates the active calibration.
- With the stock OV2640 lens, a working distance of roughly **8 to 15 cm** fills the frame with a 47 mm filter membrane. Measure and record your distance, then reuse it for both calibration and samples.
- Set focus once at that distance by turning the lens barrel until the filter texture is sharp, then lock it with the retaining ring or a small dab of hot glue.
- Mount the LED so light is diffused and even across the filter. A single point source directly above the lens creates a bright centre, specular highlights, and shadowed edges that change segmentation results.
- Enclose the sample in a dark, matt-black chamber to exclude room light, which otherwise varies between captures.

## Screenshots

Capture these views from a running instance and store them in `docs/screenshots/`:

| File | View | What it shows |
| --- | --- | --- |
| `dashboard.png` | `#/` | KPI cards, device and calibration status chips, trend chart, class donut, recent samples. |
| `new-analysis.png` | `#/new` | The three input modes: upload, ESP32-CAM capture, synthetic demo. |
| `results.png` | `#/sample/:id` | Summary panel, annotated image viewer, particle table, charts, disclaimer. |
| `history.png` | `#/history` | Sample grid with search, date filter, compare, and delete. |
| `calibration.png` | `#/calibration` | Two-point reference selection and millimetres-per-pixel history. |
| `device.png` | `#/device` | Live preview, LED control, camera settings, firmware connection values. |
| `ml-lab.png` | `#/ml` | Model status, training options, metrics, confusion matrix, feature importance. |
| `settings.png` | `#/settings` | Grouped segmentation, classification, size-bin, and device parameters. |
| `about.png` | `#/about` | Pipeline diagram, capabilities, limitations, recommended imaging setup. |

## Assumptions

These assumptions were made while building the system. Change them in **Settings** or `.env` where they do not match your setup.

- **Filter appearance.** Samples are imaged on a light membrane filter, so `background_mode` defaults to `light_filter` and particles are expected to be darker than the background. Dark-background imaging requires switching to `dark_filter`.
- **Imaging geometry is fixed.** Camera distance, focus, resolution, and filter position are assumed constant between a calibration and the samples that use it. Any change invalidates the active calibration.
- **One filter per sample.** All frames in a single analysis are assumed to be the same filter at the same scale, which is what makes per-pixel median stacking valid.
- **Frame size.** Input images are assumed to be at most 1600×1200, the ESP32-CAM UXGA maximum. Processing happens at full resolution without downscaling.
- **Accepted formats.** Only JPEG and PNG are accepted, up to `MAX_UPLOAD_MB` (default 10 MB) per file.
- **Volume is optional.** Concentration in particles per litre is reported only when a sampled volume in millilitres is supplied; otherwise it stays null rather than being estimated.
- **Default classifier.** `classifier_mode` defaults to `hybrid`. When no trained model file exists, a starter RandomForest is trained on synthetic data and is labelled as such in the UI. Its accuracy reflects synthetic variety, not your samples.
- **Microplastic size definition.** The 5 mm upper bound of the common microplastic definition is used for the largest size bin, which is flagged rather than counted silently.
- **Minimum reliable size.** Detection is treated as reliable from `min_reliable_px` (default 5 px) upward, scaled by the active millimetres-per-pixel value. Smaller particles may appear but are not considered dependable.
- **Device API key storage.** The browser keeps the device key in local storage for the current origin only. The authoritative key lives in the backend `.env` and is never sent to the browser.
- **Network trust.** The backend and the ESP32-CAM are assumed to share a trusted LAN. Device traffic is plain HTTP by design, since the camera firmware has no TLS certificate store.
- **No internet at runtime.** Chart.js is vendored at `frontend/vendor/chart.umd.js`, so the dashboard works fully offline.
- **Cross-platform storage.** All stored image paths are relative to the project root and use forward slashes, so a data directory can move between Windows, macOS, and Linux.

## Known limitations

- **No chemical identification.** A visible-light camera cannot determine polymer type. Nothing in this system identifies polyethylene, PET, or any other polymer; results are optical screening only.
- **Resolution floor.** The minimum dependable size is set by sensor resolution, lens, and working distance. Sub-micron and low-micron particles are beyond reach.
- **Transparent particles.** Clear fragments and fibres barely differ from the filter in intensity or colour, so they are frequently missed or under-measured.
- **False positives.** Dust, organic debris, mineral grains, air bubbles, textile fibres shed by clothing, and filter texture or damage all segment like particles.
- **Lighting sensitivity.** Uneven or changing illumination shifts thresholds and therefore counts. Illumination correction mitigates but does not remove this.
- **Calibration dependency.** Without an active calibration, all sizes stay in pixels and concentrations cannot be computed.
- **Touching particles.** Overlapping or aggregated particles are segmented as single objects, biasing counts down and sizes up. Closing morphology can make this worse for fibres.
- **Classifier data quality.** Model accuracy depends entirely on the diversity and correctness of verified labels and synthetic training data. It is not independent laboratory validation.
- **Single camera, single field of view.** Only what fits in one frame is analysed; there is no stage automation or mosaicking to cover a whole filter at high magnification.
- **Environmental samples are harder than lab samples.** Real water samples contain far more interfering material than the synthetic demos.
- **Local, single-user scope.** There is no authentication, no multi-user isolation, and no audit trail beyond the database timestamps. The dashboard must not be exposed to the public internet.

## Future scope

- **Fluorescence imaging.** Add a UV or blue excitation source with an emission filter; many polymers autofluoresce, which would separate plastic from most organic debris far better than brightfield rules.
- **Better optics.** A macro lens or microscope objective with a fixed working distance would lower the resolution floor and reduce edge distortion.
- **Automated filtration and staging.** A peristaltic pump with a filter holder and a motorised XY stage would give repeatable sample volumes and full-filter coverage through image mosaicking.
- **GPS and field metadata.** Record sampling coordinates, timestamp, and operator on the device so field surveys carry traceable provenance.
- **On-device TinyML.** Move a quantised shape classifier onto the ESP32 so the camera can pre-screen frames and upload only candidate particles, cutting bandwidth and storage.
- **Cloud sync and shared datasets.** Optional encrypted export of verified particle records to a central repository would let multiple sites build a shared training corpus.
- **Spectroscopy coupling.** A workflow that flags suspect particles for FTIR or Raman confirmation and records the confirmed result back against the particle would close the identification gap.

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
