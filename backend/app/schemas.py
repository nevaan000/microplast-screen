from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SampleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=250)
    volume_ml: float | None = Field(default=None, gt=0)
    filter_pore_um: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=5000)


class SampleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=250)
    volume_ml: float | None = Field(default=None, gt=0)
    filter_pore_um: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=5000)


class CalibrationCreate(BaseModel):
    pixel_distance: float = Field(gt=0)
    real_mm: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class CalibrationActivate(BaseModel):
    calibration_id: int = Field(gt=0)


class DeviceCaptureRequest(BaseModel):
    sample_id: int = Field(gt=0)
    frames: int = Field(default=1, ge=1, le=10)
    esp32_ip: str | None = Field(default=None, max_length=255)


class DeviceLedRequest(BaseModel):
    state: Literal["on", "off"]
    level: int = Field(default=255, ge=0, le=255)


class DemoRequest(BaseModel):
    name: str = Field(default="Synthetic visual screening", min_length=1, max_length=150)
    location: str | None = Field(default="Synthetic demo")
    volume_ml: float | None = Field(default=1000, gt=0)
    filter_pore_um: float | None = Field(default=20, gt=0)
    notes: str | None = Field(default="Generated synthetic filter image")
    n_particles: int = Field(default=80, ge=1, le=500)
    fibre_ratio: float = Field(default=0.35, ge=0, le=1)
    noise: float = Field(default=7, ge=0, le=50)
    lighting_gradient: float = Field(default=0.12, ge=0, le=0.8)


class ParticleUpdate(BaseModel):
    user_verified_class: Literal["fiber", "fragment", "film", "pellet", "non_plastic"] | None = None


class TrainRequest(BaseModel):
    include_synthetic: bool = True
    include_verified_particles: bool = True


class SettingsUpdate(BaseModel):
    values: dict[str, Any]

    @field_validator("values")
    @classmethod
    def require_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values:
            raise ValueError("At least one setting is required")
        return values
