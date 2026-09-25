from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import database, utc_now
from ..processing.calibration import calculate_mm_per_pixel
from ..schemas import CalibrationActivate, CalibrationCreate

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.post("", status_code=201)
def create_calibration(payload: CalibrationCreate):
    mm_per_pixel = calculate_mm_per_pixel(payload.pixel_distance, payload.real_mm)
    with database() as conn:
        conn.execute("UPDATE calibrations SET is_active = 0")
        cursor = conn.execute(
            "INSERT INTO calibrations(mm_per_pixel, pixel_distance, real_mm, note, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (mm_per_pixel, payload.pixel_distance, payload.real_mm, payload.note, utc_now()),
        )
        item = conn.execute("SELECT * FROM calibrations WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(item)


@router.get("")
def list_calibrations():
    with database() as conn:
        items = [dict(row) for row in conn.execute("SELECT * FROM calibrations ORDER BY id DESC")]
    return {"items": items, "active": next((item for item in items if item["is_active"]), None)}


@router.post("/active")
def set_active_calibration(payload: CalibrationActivate):
    with database() as conn:
        exists = conn.execute("SELECT id FROM calibrations WHERE id = ?", (payload.calibration_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Calibration not found")
        conn.execute("UPDATE calibrations SET is_active = 0")
        conn.execute("UPDATE calibrations SET is_active = 1 WHERE id = ?", (payload.calibration_id,))
        item = conn.execute("SELECT * FROM calibrations WHERE id = ?", (payload.calibration_id,)).fetchone()
    return dict(item)
