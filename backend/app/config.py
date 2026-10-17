from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _data_dir() -> str:
    # A deployed function's project directory is read-only and only /tmp is
    # writable, so the scratch directory has to move there. Records live in
    # Postgres and assets in Blob, so it stays empty in production either way.
    return os.getenv("DATA_DIR") or ("/tmp/data" if os.getenv("VERCEL") else "data")


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / _data_dir()
    database_url: str = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""
    blob_store_id: str = os.getenv("BLOB_STORE_ID", "")
    blob_token: str = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN") or ""
    asset_backend: str = os.getenv("ASSET_BACKEND", "").strip().lower()
    device_api_key: str = os.getenv("DEVICE_API_KEY", "change-this-local-device-key")
    esp32_ip: str = os.getenv("ESP32_IP", "")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "4"))
    max_concurrent_analyses: int = max(1, int(os.getenv("MAX_CONCURRENT_ANALYSES", "1")))
    admin_user: str = os.getenv("ADMIN_USER", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    session_hours: int = int(os.getenv("SESSION_HOURS", "12"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.admin_password)

    @property
    def blob_enabled(self) -> bool:
        """Assets go to Vercel Blob when a store is configured, and to DATA_DIR otherwise."""
        if self.asset_backend == "blob":
            return True
        if self.asset_backend == "local":
            return False
        return bool(self.blob_store_id or self.blob_token)

    def ensure_directories(self) -> None:
        # Only used by the local asset backend; storage.put_asset creates the
        # subfolder it needs, so there is nothing else to lay down up front.
        self.data_dir.mkdir(parents=True, exist_ok=True)


config = AppConfig()
DISCLAIMER = (
    "This is a low-cost optical screening result. It estimates particles that visually resemble "
    "microplastics and is not a laboratory-grade chemical identification. Confirm with FTIR/Raman spectroscopy."
)
