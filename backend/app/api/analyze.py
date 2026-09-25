from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import config
from ..db import active_calibration, database, get_settings
from ..schemas import DemoRequest
from .common import create_sample, decode_image, get_analysis, persist_analysis, require_sample

router = APIRouter(prefix="/api", tags=["analysis"])


def _active_mm_per_pixel() -> float | None:
    calibration = active_calibration()
    return float(calibration["mm_per_pixel"]) if calibration else None


@router.post("/analyze", status_code=201)
async def analyze_upload(
    images: list[UploadFile] = File(...),
    sample_id: int | None = Form(default=None),
    volume_ml: float | None = Form(default=None),
    name: str | None = Form(default=None),
    location: str | None = Form(default=None),
    filter_pore_um: float | None = Form(default=None),
    notes: str | None = Form(default=None),
):
    if not images:
        raise HTTPException(status_code=422, detail="At least one image is required")
    if len(images) > 10:
        raise HTTPException(status_code=422, detail="At most 10 images may be analysed together")
    frames = []
    total_bytes = 0
    for upload in images:
        content = await upload.read()
        total_bytes += len(content)
        if total_bytes > config.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Upload exceeds {config.max_upload_mb} MB total limit")
        frames.append(decode_image(content, upload.content_type))
    if sample_id is None:
        sample = create_sample({
            "name": (name or f"Analysis {datetime.now().strftime('%Y-%m-%d %H:%M')}").strip(),
            "location": location, "volume_ml": volume_ml, "filter_pore_um": filter_pore_um, "notes": notes,
        })
        sample_id = sample["id"]
    else:
        sample = require_sample(sample_id)
    if volume_ml is not None and volume_ml <= 0:
        raise HTTPException(status_code=422, detail="volume_ml must be positive")
    analysis = persist_analysis(sample_id, frames, volume_ml if volume_ml is not None else sample.get("volume_ml"), get_settings(), _active_mm_per_pixel())
    return {"sample": require_sample(sample_id), "analysis": analysis}


@router.post("/samples/{sample_id}/reanalyze")
def reanalyze_sample(sample_id: int):
    sample = require_sample(sample_id)
    with database() as conn:
        latest = conn.execute("SELECT original_path FROM analyses WHERE sample_id = ? ORDER BY id DESC LIMIT 1", (sample_id,)).fetchone()
    if latest is None:
        raise HTTPException(status_code=409, detail="Sample has no prior image to re-analyse")
    image = cv2.imread(str(config.root_dir / latest["original_path"]), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=410, detail="The stored image file is unavailable")
    analysis = persist_analysis(sample_id, [image], sample.get("volume_ml"), get_settings(), _active_mm_per_pixel())
    return {"sample": sample, "analysis": analysis}


@router.get("/images/{analysis_id}/{image_kind}")
def get_analysis_image(analysis_id: int, image_kind: str):
    if image_kind not in {"original", "annotated", "mask"}:
        raise HTTPException(status_code=404, detail="Image kind must be original, annotated, or mask")
    analysis = get_analysis(analysis_id, with_particles=False)
    path = config.root_dir / analysis[f"{image_kind}_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(path, media_type="image/png")


@router.post("/demo/generate", status_code=201)
def generate_demo(payload: DemoRequest):
    from scripts.generate_synthetic import SYNTHETIC_MM_PER_PIXEL, generate_image

    values = payload.model_dump()
    sample = create_sample({
        "name": values["name"], "location": values["location"], "volume_ml": values["volume_ml"],
        "filter_pore_um": values["filter_pore_um"], "notes": values["notes"],
    })
    image, ground_truth = generate_image({
        "n_particles": values["n_particles"], "fibre_ratio": values["fibre_ratio"], "noise": values["noise"],
        "lighting_gradient": values["lighting_gradient"],
    })
    with database() as conn:
        has_calibration = conn.execute("SELECT 1 FROM calibrations WHERE is_active = 1").fetchone() is not None
        conn.execute(
            "INSERT INTO calibrations(mm_per_pixel, pixel_distance, real_mm, note, created_at, is_active) VALUES (?, ?, ?, ?, datetime('now'), ?)",
            (SYNTHETIC_MM_PER_PIXEL, 500, 10, "Synthetic demo scale", 0 if has_calibration else 1),
        )
    analysis = persist_analysis(sample["id"], [image], sample.get("volume_ml"), get_settings(), SYNTHETIC_MM_PER_PIXEL)
    analysis["ground_truth_count"] = len(ground_truth)
    return {"sample": sample, "analysis": analysis}
