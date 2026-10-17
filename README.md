# MicroPlast Screen

MicroPlast Screen is a local visual-screening application for filter images from uploads, synthetic demos, or an ESP32-CAM. It uses OpenCV contour analysis and an optional local classifier to identify particles that **visually resemble microplastics**.

> **Scientific limitation:** This is a low-cost optical screening result, not laboratory-grade chemical or polymer identification. Confirm suspected microplastics with FTIR or Raman spectroscopy before making scientific, regulatory, or health decisions.

## Requirements

- Python 3.10 or newer
- A Postgres server — a local Docker container or a free Neon branch
- A current desktop browser
- An ESP32-CAM and a USB-to-UART adapter only for camera capture
- PlatformIO only for firmware builds and flashing

No Node.js installation is required. The backend serves the static frontend itself. Every record lives in Postgres; images and the trained classifier go to a Vercel Blob store when one is configured and to `DATA_DIR` otherwise.

## Start the application

Run these commands from the project root.

### 1. Provide a database

The application refuses to start without `DATABASE_URL`. Start a throwaway Postgres in Docker:

```sh
docker run -d --name mps-postgres -e POSTGRES_USER=microplast -e POSTGRES_PASSWORD=microplast_dev_only -e POSTGRES_DB=microplast -p 5433:5432 postgres:17-alpine
```

then create `.env` from the template and set:

```
DATABASE_URL=postgresql://microplast:microplast_dev_only@127.0.0.1:5433/microplast
```

Any Postgres 13 or newer works, including a free Neon branch — use its pooled (`-pooler`) connection string. Tables and indexes are created on first boot.

### 2. Start the server

#### Windows

```bat
run.bat
```

#### macOS and Linux

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

- `DATABASE_URL`: required Postgres connection string. `POSTGRES_URL` is accepted as an alias.
- `BLOB_STORE_ID` / `BLOB_READ_WRITE_TOKEN`: the Vercel Blob store that holds images and the trained classifier. Leave both empty to keep assets on disk instead.
- `ASSET_BACKEND`: force `blob` or `local` regardless of the two values above.
- `DATA_DIR`: local asset root, defaulting to `data`, and to `/tmp/data` on Vercel where the project directory is read-only.
- `DEVICE_API_KEY`: shared credential for device-control and device-upload requests.
- `ESP32_IP`: camera hostname or IP address, optionally with a port; do not include `http://`.
- `MAX_UPLOAD_MB`: maximum accepted upload size. The default of 4 MB sits under the 4.5 MB request body that Vercel rejects at the edge before the application can answer.
- `MAX_CONCURRENT_ANALYSES`: how many analyses may run at once, default 1. Extra requests wait for a free slot and return `503` if none opens within 90 seconds. Raise it only on hosts with memory to spare.
- `ADMIN_USER` / `ADMIN_PASSWORD`: dashboard login. Leave the password empty for local use without a login; set it before publishing.
- `SESSION_HOURS`: how long a sign-in session stays valid, default 12.

Records — samples, analyses, particles, calibrations, settings, and sessions — live in Postgres. Assets — uploaded originals, annotated images, masks, and the classifier — live in the Blob store under `raw/`, `processed/`, `masks/`, and `models/`, or in the same-named folders under `DATA_DIR` when no store is configured. Delete samples through the History page so records and assets are removed together.

Every stored asset path is relative and uses forward slashes, so the same database rows resolve against either backend — a laptop's `data/` folder or a private Blob store.

## Publishing

The backend serves the dashboard itself, so one deployment gives a single public URL for both the UI and the API.

### Vercel (free)

The Python runtime loads `main.py` at the project root, which re-exports the FastAPI `app`. `vercel.json` sets a 300-second `maxDuration` — an analysis of ten 1600×1200 frames needs it — and keeps firmware, docs, tests, and the local data folder out of the function bundle.

1. **Create a Neon database.** In the Vercel dashboard choose **Storage → Create Database → Neon** and attach it to the project. Vercel then sets `POSTGRES_URL`, which the application reads as an alias for `DATABASE_URL`; if you paste a connection string yourself, use the pooled (`-pooler`) one.
2. **Create a Blob store.** Choose **Storage → Create Store → Blob** and select **private**. Visibility cannot be changed afterwards, and this app serves every asset through an authenticated route, so a public store would protect sample images with nothing but unguessable URLs. Attaching the store sets `BLOB_STORE_ID` and `BLOB_READ_WRITE_TOKEN`.
3. **Add the secrets.** In **Project → Settings → Environment Variables** set `ADMIN_PASSWORD` to a long random value — without it the dashboard is published with no login at all — and `DEVICE_API_KEY` to a generated key (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), which also goes into `firmware/esp32-cam/include/secrets.h`.
4. **Import the repository** and deploy. There is no build command and no output directory; `requirements.txt` and `.python-version` are detected automatically.

The free tier shapes the deployment in ways worth knowing:

- **Hobby functions get 1024 MB in a single region.** `MAX_CONCURRENT_ANALYSES=1` keeps a maximum-size analysis inside that budget, and further analyses queue behind it.
- **A request body above 4.5 MB is refused at the edge**, so `MAX_UPLOAD_MB` defaults to 4 and the dashboard rejects an oversized selection before posting it. Responses share that cap but streaming is exempt, which is why images and exports are streamed.
- **The project directory is read-only, and `/tmp` does not survive between invocations.** Assets therefore go to Blob and records to Postgres. A device capture's frames wait in the store under a `raw/session-…` prefix rather than on disk, so frames that land on different instances still meet up.
- **Blob's free allowance is 1 GB of storage and 10,000 simple operations a month**, and each image the dashboard displays costs one read.
- **Nothing retrains on a cold start.** The starter classifier is trained once into `models/` in the store and reloaded per instance, so a redeploy keeps it — along with any model retrained in the ML lab.
- **Sign-in rate limiting is per instance.** The failed-attempt counter lives in one function's memory, so it slows a casual attack rather than stopping a distributed one. A strong `ADMIN_PASSWORD` is what actually protects the dashboard.

### Container host

Build and run the image locally, against the same Postgres:

```sh
docker build -t microplast-screen .
docker run --rm -p 8000:8000 -v microplast-data:/data \
  -e DATABASE_URL=postgresql://microplast:microplast_dev_only@host.docker.internal:5433/microplast \
  -e ADMIN_PASSWORD=pick-a-long-password -e DEVICE_API_KEY=pick-a-device-key microplast-screen
```

Generated images and the trained classifier live in the `/data` volume; without one they disappear when the container is replaced, and every boot retrains the starter classifier for about 20 seconds. Set `BLOB_STORE_ID` and `BLOB_READ_WRITE_TOKEN` instead to keep assets in Blob and run as many instances as you like.

#### Render

`render.yaml` describes the deployment as a Render Blueprint: a Docker web service, a 1 GB persistent disk mounted at `/data`, a health check on `/api/health`, and the environment variables the service needs.

1. Push this repository to GitHub.
2. In Render choose **New → Blueprint**, connect the repository, and apply it. Render reads `render.yaml` and prompts for `ADMIN_PASSWORD` and `DATABASE_URL`; enter a long random password and the pooled connection string of a Postgres (a free Neon branch works). `DEVICE_API_KEY` is generated once — copy it from the service's Environment tab into `firmware/esp32-cam/include/secrets.h`.
3. When the build finishes, open `https://<service-name>.onrender.com` and sign in.

The blueprint deliberately leaves out `ADMIN_USER`, `SESSION_HOURS`, `MAX_UPLOAD_MB`, `MAX_CONCURRENT_ANALYSES`, `BLOB_STORE_ID`, `BLOB_READ_WRITE_TOKEN`, and `ESP32_IP` so their code defaults keep applying; add them in the service's Environment tab if you need to override one.

Three settings in the blueprint are deliberate:

- **A persistent disk requires a paid instance**, so `plan` is `starter`, the cheapest tier that can mount `/data`. On the free plan the disk cannot be attached at all, and every deploy or restart discards the uploaded images and any retrained classifier.
- **`numInstances` must stay at 1.** The image files live on the instance's own disk, so a second replica would keep a separate set of assets behind the same database rows. Configure a Blob store to lift that restriction.
- **Analyses are queued, not run in parallel**, because a starter instance has 512 MB of memory. Measured at exactly 0.5 CPU and 512 MB, two and three simultaneous maximum-size uploads — ten 1600×1200 frames each — completed with no OOM kill, peaking at 399–449 MiB of process memory, while `/api/health` answered every probe in under 300 ms. Under three-way load the 90 s queue wait is occasionally exceeded and a request is shed with `503`. Offloading the work off the event loop matters as much as the queue: without it, the same two-way load blocked `/api/health` for 30 s at a time, which is enough for a platform health check to fail and restart the instance. The image also caps malloc arenas and BLAS threads, worth a further ~35 MiB at peak. Raise `MAX_CONCURRENT_ANALYSES` only on a larger plan.

#### Railway and Fly.io

Deploy the repository as a Docker service, attach a persistent volume mounted at `/data` (Fly.io `fly.toml`: `mounts: source = "microplast_data"`, `destination = "/data"`; Railway: add a volume with mount path `/data`), set `DATABASE_URL`, `ADMIN_PASSWORD` and `DEVICE_API_KEY`, and keep a single instance. Let the platform terminate HTTPS. Set `PORT` only if the platform requires a specific value; the image honours it.

Point the ESP32-CAM at the public address by setting `SERVER_URL` in `firmware/esp32-cam/include/secrets.h` to the HTTPS URL, for example `https://microplast-screen.onrender.com`. The firmware authenticates with `DEVICE_API_KEY`, exactly as on the LAN, and device upload is exempt from the session-cookie login precisely so the camera can post without signing in.

One caveat applies to TLS on the camera: `uploader.cpp` calls `HTTPClient::begin()` with no certificate authority supplied, so the ESP32 Arduino core opens the TLS connection **without validating the server certificate**. Traffic is encrypted against a passive listener, but the `DEVICE_API_KEY` is not protected from an attacker who can spoof DNS on the camera's network path. If that matters for your deployment, bundle a root CA with the firmware and pass it to `WiFiClientSecure::setCACert()`, or keep the camera on a LAN that reaches the backend over plain HTTP.

Never publish an instance without `ADMIN_PASSWORD`: anyone who learns the URL could read, upload, and delete samples.

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

Set `WIFI_SSID`, `WIFI_PASS`, `DEVICE_NAME`, `SERVER_URL`, and `DEVICE_API_KEY` in `secrets.h`. `SERVER_URL` is the LAN address of the computer running this backend, including its port, such as `http://192.168.1.50:8000`, or the public HTTPS URL when the backend is published (see [Publishing on a container host](#publishing-on-a-container-host)). The firmware and backend `DEVICE_API_KEY` values must match exactly.

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

PlatformIO normally detects the connected serial adapter. If it cannot, identify the adapter with `python -m platformio device list`, then set the correct upload port in PlatformIO for that connected board before retrying. On a LAN deployment the camera and server must use the same trusted network.

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
- **Accepted formats.** Only JPEG and PNG are accepted, up to `MAX_UPLOAD_MB` (default 4 MB) across all frames of one request.
- **Volume is optional.** Concentration in particles per litre is reported only when a sampled volume in millilitres is supplied; otherwise it stays null rather than being estimated.
- **Default classifier.** `classifier_mode` defaults to `hybrid`. When no trained model file exists, a starter RandomForest is trained on synthetic data and is labelled as such in the UI. Its accuracy reflects synthetic variety, not your samples.
- **Microplastic size definition.** The 5 mm upper bound of the common microplastic definition is used for the largest size bin, which is flagged rather than counted silently.
- **Minimum reliable size.** Detection is treated as reliable from `min_reliable_px` (default 5 px) upward, scaled by the active millimetres-per-pixel value. Smaller particles may appear but are not considered dependable.
- **Device API key storage.** The browser keeps the device key in local storage for the current origin only. The authoritative key lives in the backend `.env` and is never sent to the browser.
- **Network trust.** Device traffic between the camera and the backend is plain HTTP on a LAN by design, since the firmware has no certificate store; over a public HTTPS address the connection is encrypted but the server certificate is not validated. Dashboard traffic in public mode relies on the host terminating TLS.
- **No third-party CDN at runtime.** Chart.js is vendored at `frontend/vendor/chart.umd.js`, so the dashboard loads no external script. The backend still has to reach its Postgres, and Blob when a store is configured.
- **Portable asset paths.** Stored asset paths are relative and use forward slashes, so the same database rows resolve under `DATA_DIR` on Windows, macOS, or Linux, in a container volume mounted outside the project directory, or in a Blob store.

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
- **Single-user scope.** The optional login is one shared account, not a multi-user system: there is no per-user isolation, no role separation, and no audit trail beyond the database timestamps. With assets on a local disk the service must also run as a single instance; configuring a Blob store lifts that.
- **Live camera control needs network reach.** The Device page's preview, LED, capture, and camera-settings calls are made *by the backend* to `http://<camera>/…`. A publicly hosted backend cannot route to a private LAN address such as `192.168.1.50`, so those controls report the camera as offline. This is a network constraint, not a software fault. The reverse direction is unaffected: the camera pushes captures to the public HTTPS URL and they are analysed normally. To drive a LAN camera remotely you would need to expose it through a tunnel, which also requires allowing an `https://` camera address in `device.py`.
- **Analyses are serialised by default.** A second capture waits for the first to finish instead of running alongside it, so if several cameras upload at once the last one can wait tens of seconds — longer than the firmware's 20 s HTTP timeout — and a request that gets no slot within 90 seconds is shed with `503`. The backend keeps working after a camera disconnects, so a timed-out upload is still analysed and stored; the firmware's retry can therefore leave two analyses for one sample, and the dashboard shows the latest. Raise `MAX_CONCURRENT_ANALYSES` once the host has memory to spare.
- **The queue is per process.** `MAX_CONCURRENT_ANALYSES` is a semaphore inside one instance, so a host running several instances allows that many analyses at once and the memory ceiling applies per instance rather than overall.
- **Serverless storage costs an operation per read.** With assets in Blob, displaying a sample's three images is three reads against the monthly allowance, and a cold instance re-reads the trained classifier.

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

The suite needs a Postgres it can truncate; the container from step 1 works. Run it from the project root:

```sh
python -m pytest backend/tests
```

`backend/tests/conftest.py` points `DATABASE_URL` at `postgresql://microplast:microplast_dev_only@127.0.0.1:5433/microplast` unless `TEST_DATABASE_URL` says otherwise. It never falls back to an inherited connection string, because the fixture truncates every table. Assets stay on disk under `data/` (`ASSET_BACKEND=local`), so a run spends no Blob quota and needs no network access.

The suite covers the image pipeline, circular ROI handling, calibration behaviour, API upload/export/delete flow, device-upload authentication, the concurrency guard, and the asset-storage layout.
