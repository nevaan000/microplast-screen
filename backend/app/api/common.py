from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException

from ..config import config
from ..db import database, utc_now
from ..processing.pipeline import analyze_frames


def row_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_sample(values: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with database() as conn:
        cursor = conn.execute(
            "INSERT INTO samples(name, location, volume_ml, filter_pore_um, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (values["name"], values.get("location"), values.get("volume_ml"), values.get("filter_pore_um"), values.get("notes"), now, now),
        )
        row = conn.execute("SELECT * FROM samples WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def require_sample(sample_id: int) -> dict[str, Any]:
    with database() as conn:
        row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return dict(row)


def decode_image(content: bytes, content_type: str | None = None) -> np.ndarray:
    if not content:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(content) > config.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds {config.max_upload_mb} MB upload limit")
    if content_type and content_type.split(";", 1)[0].lower() not in {"image/jpeg", "image/jpg", "image/png", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG images are accepted")
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a decodable JPEG or PNG image")
    return image


def _write_image(directory: Path, prefix: str, image: np.ndarray) -> str:
    filename = f"{prefix}-{uuid.uuid4().hex}.png"
    target = directory / filename
    if not cv2.imwrite(str(target), image):
        raise RuntimeError(f"Could not write image {target.name}")
    return target.relative_to(config.root_dir).as_posix()


def persist_analysis(
    sample_id: int,
    frames: list[np.ndarray],
    volume_ml: float | None,
    settings: dict[str, Any],
    mm_per_pixel: float | None,
) -> dict[str, Any]:
    result = analyze_frames(frames, settings=settings, mm_per_pixel=mm_per_pixel, volume_ml=volume_ml)
    original_path = _write_image(config.raw_dir, "analysis", result["source"])
    annotated_path = _write_image(config.processed_dir, "analysis", result["annotated"])
    mask_path = _write_image(config.masks_dir, "analysis", result["mask"])
    summary = result["summary"]
    now = utc_now()
    with database() as conn:
        cursor = conn.execute(
            """INSERT INTO analyses(
                sample_id, created_at, n_frames, image_w, image_h, mm_per_pixel, settings_json, classifier_mode,
                total_particles, suspected_plastic, non_plastic, fibers, fragments, films, pellets,
                mean_length_mm, median_length_mm, concentration_per_l, sample_confidence, min_reliable_size_mm,
                processing_ms, original_path, annotated_path, mask_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_id, now, result["n_frames"], result["source"].shape[1], result["source"].shape[0], mm_per_pixel,
                json.dumps(settings), settings.get("classifier_mode", "hybrid"), summary["total_particles"], summary["suspected_plastic"],
                summary["non_plastic"], summary["fibers"], summary["fragments"], summary["films"], summary["pellets"],
                summary["mean_length_mm"], summary["median_length_mm"], summary["concentration_per_l"], summary["sample_confidence"],
                summary["min_reliable_size_mm"], summary["processing_ms"], original_path, annotated_path, mask_path,
            ),
        )
        analysis_id = cursor.lastrowid
        for particle in result["particles"]:
            conn.execute(
                """INSERT INTO particles(
                    analysis_id, idx, centroid_x, centroid_y, bbox_x, bbox_y, bbox_w, bbox_h, area_px, perimeter_px,
                    length_px, width_px, aspect_ratio, circularity, solidity, extent, mean_r, mean_g, mean_b, mean_h,
                    mean_s, mean_v, color_name, texture_std, length_mm, width_mm, area_mm2, shape_class, label, confidence,
                    user_verified_class, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id, particle["idx"], particle["centroid_x"], particle["centroid_y"], particle["bbox_x"], particle["bbox_y"],
                    particle["bbox_w"], particle["bbox_h"], particle["area_px"], particle["perimeter_px"], particle["length_px"],
                    particle["width_px"], particle["aspect_ratio"], particle["circularity"], particle["solidity"], particle["extent"],
                    particle["mean_r"], particle["mean_g"], particle["mean_b"], particle["mean_h"], particle["mean_s"], particle["mean_v"],
                    particle["color_name"], particle["texture_std"], particle["length_mm"], particle["width_mm"], particle["area_mm2"],
                    particle["shape_class"], particle["label"], particle["confidence"], None, now,
                ),
            )
        analysis = dict(conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone())
        particles = [dict(row) for row in conn.execute("SELECT * FROM particles WHERE analysis_id = ? ORDER BY idx", (analysis_id,))]
    analysis["settings"] = json.loads(analysis.pop("settings_json"))
    analysis["size_histogram"] = summary["size_histogram"]
    analysis["particles"] = particles
    return analysis


def get_analysis(analysis_id: int, with_particles: bool = True) -> dict[str, Any]:
    with database() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        particles = [dict(item) for item in conn.execute("SELECT * FROM particles WHERE analysis_id = ? ORDER BY idx", (analysis_id,))] if row and with_particles else []
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = dict(row)
    analysis["settings"] = json.loads(analysis.pop("settings_json"))
    if with_particles:
        analysis["particles"] = particles
    return analysis


def response_for_sample(sample_id: int) -> dict[str, Any]:
    sample = require_sample(sample_id)
    with database() as conn:
        latest = conn.execute("SELECT id FROM analyses WHERE sample_id = ? ORDER BY id DESC LIMIT 1", (sample_id,)).fetchone()
    return {"sample": sample, "analysis": get_analysis(latest["id"]) if latest else None}


def delete_asset(relative_path: str) -> None:
    path = (config.root_dir / relative_path).resolve()
    data_root = config.data_dir.resolve()
    if data_root not in path.parents:
        return
    if path.exists() and path.is_file():
        path.unlink()
