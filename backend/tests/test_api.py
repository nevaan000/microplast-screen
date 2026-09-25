import cv2
from fastapi.testclient import TestClient

from backend.app.main import app
from scripts.generate_synthetic import generate_image


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
