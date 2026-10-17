from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient

from backend.app.api import common
from backend.app.config import config
from backend.app.db import initialize_database
from backend.app.main import app
from scripts.generate_synthetic import SYNTHETIC_MM_PER_PIXEL, generate_image


def _jpeg_bytes():
    image, _ = generate_image({"width": 800, "height": 600, "n_particles": 18, "noise": 0, "seed": 12})
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_sample_upload_result_export_and_delete(clean_data):
    with TestClient(app) as client:
        created = client.post("/api/samples", json={"name": "API sample", "volume_ml": 250, "location": "Test lab"})
        assert created.status_code == 201
        sample_id = created.json()["id"]
        response = client.post(
            "/api/analyze",
            data={"sample_id": str(sample_id)},
            files=[("images", ("filter.jpg", _jpeg_bytes(), "image/jpeg"))],
        )
        assert response.status_code == 201
        analysis = response.json()["analysis"]
        assert analysis["total_particles"] > 0
        detail = client.get(f"/api/samples/{sample_id}")
        assert detail.status_code == 200
        assert detail.json()["analysis"]["particles"]
        assert client.get(f"/api/images/{analysis['id']}/annotated").headers["content-type"] == "image/png"
        for suffix, content_type in (("csv", "text/csv"), ("json", "application/json"), ("pdf", "application/pdf")):
            exported = client.get(f"/api/export/{sample_id}.{suffix}")
            assert exported.status_code == 200
            assert content_type in exported.headers["content-type"]
            assert b"low-cost optical screening" in exported.content or suffix == "pdf"
        assert client.delete(f"/api/samples/{sample_id}").status_code == 204
        assert client.get(f"/api/samples/{sample_id}").status_code == 404


def test_device_upload_auth_and_invalid_file(clean_data):
    with TestClient(app) as client:
        sample = client.post("/api/samples", json={"name": "Device sample"}).json()
        sample_id = sample["id"]
        headers = {"X-Sample-Id": str(sample_id), "Content-Type": "image/jpeg"}
        assert client.post("/api/device/upload", content=_jpeg_bytes(), headers=headers).status_code == 401
        headers["X-API-Key"] = "change-this-local-device-key"
        uploaded = client.post("/api/device/upload", content=_jpeg_bytes(), headers=headers)
        assert uploaded.status_code == 201
        assert uploaded.json()["analysis"] is not None
        bad = client.post("/api/analyze", files=[("images", ("bad.txt", b"not-an-image", "text/plain"))])
        assert bad.status_code in {400, 415}
        client.delete(f"/api/samples/{sample_id}")


def test_demo_does_not_create_a_calibration(clean_data):
    with TestClient(app) as client:
        before = client.get("/api/calibration").json()
        demo = client.post("/api/demo/generate", json={"name": "Demo scale check", "n_particles": 12, "noise": 0})
        assert demo.status_code == 201
        body = demo.json()
        # The demo is scaled with the synthetic constant handed to the pipeline...
        assert body["analysis"]["mm_per_pixel"] == pytest.approx(SYNTHETIC_MM_PER_PIXEL)
        # ...but it must never be recorded as, or promoted to, a camera calibration,
        # otherwise the next real upload inherits a fabricated mm-per-pixel scale.
        after = client.get("/api/calibration").json()
        assert len(after["items"]) == len(before["items"])
        assert after["active"] == before["active"]
        assert client.delete(f"/api/samples/{body['sample']['id']}").status_code == 204


def test_asset_paths_survive_a_data_directory_outside_the_app_root(clean_data):
    """A container mounts DATA_DIR outside the code directory, so stored paths must resolve against it."""
    with TestClient(app) as client:
        sample_id = client.post("/api/samples", json={"name": "Volume mount", "volume_ml": 100}).json()["id"]
        response = client.post(
            "/api/analyze",
            data={"sample_id": str(sample_id)},
            files=[("images", ("filter.jpg", _jpeg_bytes(), "image/jpeg"))],
        )
        assert response.status_code == 201
        analysis = response.json()["analysis"]

        stored = Path(analysis["annotated_path"])
        assert not stored.is_absolute()
        assert stored.parts[0] == "processed"
        annotated = config.data_dir / stored
        assert annotated.is_file()

        assert client.post(f"/api/samples/{sample_id}/reanalyze").status_code == 200
        assert client.delete(f"/api/samples/{sample_id}").status_code == 204
        assert not annotated.exists()


def test_a_saturated_analysis_slot_returns_503_and_leaves_the_api_responsive(clean_data, monkeypatch):
    """A second concurrent maximum-size analysis is what OOM-kills a 512 MB instance."""
    monkeypatch.setattr(common, "SLOT_WAIT_SECONDS", 0.05)
    assert common.ANALYSIS_SLOTS.acquire(timeout=5)
    try:
        with TestClient(app) as client:
            response = client.post("/api/demo/generate", json={"name": "Queued", "n_particles": 8, "noise": 0})
            assert response.status_code == 503
            assert "retry" in response.json()["detail"].lower()
            assert client.get("/api/health").status_code == 200
    finally:
        common.ANALYSIS_SLOTS.release()


def test_concurrent_analyses_are_queued_and_release_their_slot(clean_data):
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(client.post, "/api/demo/generate", json={"name": f"Concurrent {index}", "n_particles": 10, "noise": 0})
            for index in range(2)
        ]
        statuses = [future.result(timeout=180).status_code for future in futures]
    assert statuses == [201, 201]
    assert common.ANALYSIS_SLOTS.acquire(timeout=5), "analysis slot was not released"
    common.ANALYSIS_SLOTS.release()


def test_rerunning_the_schema_keeps_existing_rows(clean_data):
    """Every function cold start applies the DDL again to a database that already has data."""
    with TestClient(app) as client:
        sample_id = client.post("/api/samples", json={"name": "Survives a cold start"}).json()["id"]
        initialize_database()
        assert client.get(f"/api/samples/{sample_id}").status_code == 200
        assert client.get("/api/settings").status_code == 200
        assert client.delete(f"/api/samples/{sample_id}").status_code == 204


def test_health_publishes_an_upload_cap_the_platform_will_accept(clean_data):
    """Vercel returns its own 413 at the edge above 4.5 MB, before our check can answer."""
    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["max_upload_mb"] == config.max_upload_mb
    assert body["max_upload_mb"] <= 4
