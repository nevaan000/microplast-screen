from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / os.getenv("DATA_DIR", "data")
    device_api_key: str = os.getenv("DEVICE_API_KEY", "change-this-local-device-key")
    esp32_ip: str = os.getenv("ESP32_IP", "")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "microplastic.db"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def masks_dir(self) -> Path:
        return self.data_dir / "masks"

    @property
    def calibration_dir(self) -> Path:
        return self.data_dir / "calibration"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.raw_dir, self.processed_dir, self.masks_dir, self.calibration_dir, self.exports_dir):
            directory.mkdir(parents=True, exist_ok=True)


config = AppConfig()
DISCLAIMER = (
    "This is a low-cost optical screening result. It estimates particles that visually resemble "
    "microplastics and is not a laboratory-grade chemical identification. Confirm with FTIR/Raman spectroscopy."
)
