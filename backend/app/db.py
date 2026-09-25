from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import config

DEFAULT_SETTINGS: dict[str, Any] = {
    "illumination_correction": True,
    "background_mode": "light_filter",
    "threshold_method": "otsu",
    "fixed_threshold": 125,
    "adaptive_block_size": 31,
    "adaptive_c": 4,
    "sat_threshold": 60,
    "opening_kernel": 3,
    "opening_iterations": 1,
    "closing_kernel": 3,
    "closing_iterations": 2,
    "min_area_px": 12,
    "max_area_percent": 25,
    "border_margin_percent": 3,
    "roi_mode": "none",
    "roi_center_x": 0.5,
    "roi_center_y": 0.5,
    "roi_radius_percent": 48,
    "plastic_threshold": 0.55,
    "classifier_mode": "hybrid",
    "fiber_aspect_ratio": 3.0,
    "fiber_width_px": 12,
    "fiber_width_mm": 0.3,
    "min_reliable_px": 5,
    "size_bins_mm": [0.2, 0.5, 1.0, 2.0, 5.0],
    "esp32_ip": config.esp32_ip,
    "camera_framesize": "UXGA",
    "camera_quality": 10,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    config.ensure_directories()
    connection = sqlite3.connect(config.db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with database() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                volume_ml REAL,
                filter_pore_um REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                n_frames INTEGER NOT NULL,
                image_w INTEGER NOT NULL,
                image_h INTEGER NOT NULL,
                mm_per_pixel REAL,
                settings_json TEXT NOT NULL,
                classifier_mode TEXT NOT NULL,
                total_particles INTEGER NOT NULL,
                suspected_plastic INTEGER NOT NULL,
                non_plastic INTEGER NOT NULL,
                fibers INTEGER NOT NULL,
                fragments INTEGER NOT NULL,
                films INTEGER NOT NULL,
                pellets INTEGER NOT NULL,
                mean_length_mm REAL,
                median_length_mm REAL,
                concentration_per_l REAL,
                sample_confidence REAL,
                min_reliable_size_mm REAL,
                processing_ms REAL NOT NULL,
                original_path TEXT NOT NULL,
                annotated_path TEXT NOT NULL,
                mask_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS particles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                idx INTEGER NOT NULL,
                centroid_x REAL NOT NULL,
                centroid_y REAL NOT NULL,
                bbox_x INTEGER NOT NULL,
                bbox_y INTEGER NOT NULL,
                bbox_w INTEGER NOT NULL,
                bbox_h INTEGER NOT NULL,
                area_px REAL NOT NULL,
                perimeter_px REAL NOT NULL,
                length_px REAL NOT NULL,
                width_px REAL NOT NULL,
                aspect_ratio REAL NOT NULL,
                circularity REAL NOT NULL,
                solidity REAL NOT NULL,
                extent REAL NOT NULL,
                mean_r REAL NOT NULL,
                mean_g REAL NOT NULL,
                mean_b REAL NOT NULL,
                mean_h REAL NOT NULL,
                mean_s REAL NOT NULL,
                mean_v REAL NOT NULL,
                color_name TEXT NOT NULL,
                texture_std REAL NOT NULL,
                length_mm REAL,
                width_mm REAL,
                area_mm2 REAL,
                shape_class TEXT NOT NULL,
                label TEXT NOT NULL,
                confidence REAL NOT NULL,
                user_verified_class TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calibrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mm_per_pixel REAL NOT NULL,
                pixel_distance REAL NOT NULL,
                real_mm REAL NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_analyses_sample_id ON analyses(sample_id);
            CREATE INDEX IF NOT EXISTS idx_particles_analysis_id ON particles(analysis_id);
            """
        )
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value_json) VALUES (?, ?)",
                (key, json.dumps(value)),
            )


def get_settings() -> dict[str, Any]:
    with database() as conn:
        rows = conn.execute("SELECT key, value_json FROM settings").fetchall()
    values = DEFAULT_SETTINGS.copy()
    values.update({row["key"]: json.loads(row["value_json"]) for row in rows if row["key"] in DEFAULT_SETTINGS})
    return values


def update_settings(values: dict[str, Any]) -> dict[str, Any]:
    allowed = set(DEFAULT_SETTINGS)
    with database() as conn:
        for key, value in values.items():
            if key in allowed:
                conn.execute(
                    "INSERT INTO settings(key, value_json) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                    (key, json.dumps(value)),
                )
    return get_settings()


def reset_settings() -> dict[str, Any]:
    with database() as conn:
        conn.execute("DELETE FROM settings")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT INTO settings(key, value_json) VALUES (?, ?)", (key, json.dumps(value)))
    return get_settings()


def active_calibration() -> sqlite3.Row | None:
    with database() as conn:
        return conn.execute("SELECT * FROM calibrations WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
