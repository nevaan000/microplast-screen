import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
from fastapi.testclient import TestClient

from backend.app.config import config
from backend.app.db import update_settings
from backend.app.main import app
from scripts.generate_synthetic import generate_image


def _jpeg_bytes():
    image, _ = generate_image({"width": 800, "height": 600, "n_particles": 12, "noise": 0, "seed": 5})
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


class StubEsp32Handler(BaseHTTPRequestHandler):
    calls: list[tuple[str, dict[str, list[str]]]] = []
    jpeg = b""

    def do_GET(self):
        parsed = urlparse(self.path)
        type(self).calls.append((parsed.path, parse_qs(parsed.query)))
        if parsed.path == "/config":
            body, content_type, status = b'{"ok":true}', "application/json", 200
        elif parsed.path == "/capture":
            body, content_type, status = type(self).jpeg, "image/jpeg", 200
        else:
            body, content_type, status = b'{"detail":"Not found"}', "application/json", 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_capture_applies_saved_camera_defaults_before_frames(clean_data):
    StubEsp32Handler.calls = []
    StubEsp32Handler.jpeg = _jpeg_bytes()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubEsp32Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f"127.0.0.1:{server.server_address[1]}"
    try:
        update_settings({"esp32_ip": host, "camera_framesize": "SVGA", "camera_quality": 21})
        with TestClient(app) as client:
            sample_id = client.post("/api/samples", json={"name": "Camera defaults"}).json()["id"]
            response = client.post(
                "/api/device/capture",
                json={"sample_id": sample_id, "frames": 2},
                headers={"X-API-Key": config.device_api_key},
            )
            assert response.status_code == 201
            assert response.json()["analysis"]["id"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    paths = [path for path, _ in StubEsp32Handler.calls]
    assert paths[0] == "/config"
    assert paths.count("/capture") == 2
    assert StubEsp32Handler.calls[0][1] == {"framesize": ["SVGA"], "quality": ["21"]}


def test_capture_rejects_missing_api_key(clean_data):
    with TestClient(app) as client:
        sample_id = client.post("/api/samples", json={"name": "Unauthorised"}).json()["id"]
        response = client.post("/api/device/capture", json={"sample_id": sample_id, "frames": 1})
        assert response.status_code == 401
        client.delete(f"/api/samples/{sample_id}")
