from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api import auth
from backend.app.config import AppConfig
from backend.app.main import app


def _enable_auth(monkeypatch, password="test-password"):
    secured = AppConfig(admin_password=password)
    monkeypatch.setattr("backend.app.main.config", secured)
    monkeypatch.setattr("backend.app.api.auth.config", secured)
    auth._failures.clear()
    return secured


def test_protected_routes_require_a_session(clean_data, monkeypatch):
    _enable_auth(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/samples").status_code == 401
        assert client.get("/api/settings").status_code == 401
        assert client.get("/docs").status_code == 401
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 200
        me = client.get("/api/auth/me").json()
        assert me == {"auth_enabled": True, "authenticated": False, "user": None}


def test_login_logout_and_session_cookie(clean_data, monkeypatch):
    _enable_auth(monkeypatch)
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
        response = client.post("/api/auth/login", json={"username": "admin", "password": "test-password"})
        assert response.status_code == 200
        cookie = response.headers.get("set-cookie", "")
        assert "httponly" in cookie.lower() and "samesite=lax" in cookie.lower()
        assert client.get("/api/samples").status_code == 200
        assert client.get("/api/auth/me").json()["authenticated"] is True
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/samples").status_code == 401


def test_failed_logins_are_rate_limited(clean_data, monkeypatch):
    _enable_auth(monkeypatch)
    with TestClient(app) as client:
        codes = [
            client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).status_code
            for _ in range(auth.MAX_FAILURES_PER_WINDOW + 1)
        ]
    assert codes[: auth.MAX_FAILURES_PER_WINDOW] == [401] * auth.MAX_FAILURES_PER_WINDOW
    assert codes[-1] == 429
    auth._failures.clear()


def test_device_upload_still_uses_the_device_key(clean_data, monkeypatch):
    _enable_auth(monkeypatch)
    with TestClient(app) as client:
        # No session cookie and no device key: the rejection must come from device
        # auth, proving uploads are not gated behind the browser session.
        response = client.post("/api/device/upload", content=b"not-an-image", headers={"Content-Type": "image/jpeg"})
        assert response.status_code == 401
        assert response.json()["detail"] != "Authentication required"


def test_no_login_required_without_a_password(clean_data):
    with TestClient(app) as client:
        assert client.get("/api/auth/me").json() == {"auth_enabled": False, "authenticated": True, "user": None}
        assert client.get("/api/samples").status_code == 200
