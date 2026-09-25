from __future__ import annotations

from fastapi import APIRouter

from ..config import DISCLAIMER
from ..db import database

router = APIRouter(prefix="/api/stats", tags=["statistics"])


@router.get("/overview")
def overview():
    latest = "SELECT a.* FROM analyses a WHERE a.id = (SELECT id FROM analyses WHERE sample_id = a.sample_id ORDER BY id DESC LIMIT 1)"
    with database() as conn:
        samples = conn.execute("SELECT COUNT(*) AS count FROM samples").fetchone()["count"]
        totals = conn.execute(f"SELECT COALESCE(SUM(total_particles), 0) AS total, COALESCE(SUM(suspected_plastic), 0) AS suspected FROM ({latest})").fetchone()
        recent = [dict(row) for row in conn.execute(
            f"""SELECT s.id, s.name, s.created_at, a.id AS analysis_id, a.total_particles, a.suspected_plastic,
                       a.concentration_per_l, a.annotated_path FROM samples s LEFT JOIN ({latest}) a ON a.sample_id = s.id
                ORDER BY s.created_at DESC LIMIT 8"""
        )]
        timeline = [dict(row) for row in conn.execute(
            f"""SELECT s.id, s.name, s.created_at, a.suspected_plastic FROM samples s JOIN ({latest}) a ON a.sample_id = s.id
                ORDER BY s.created_at ASC"""
        )]
        classes = conn.execute(
            f"SELECT COALESCE(SUM(fibers), 0) AS fibers, COALESCE(SUM(fragments), 0) AS fragments, COALESCE(SUM(films), 0) AS films, COALESCE(SUM(pellets), 0) AS pellets, COALESCE(SUM(non_plastic), 0) AS non_plastic FROM ({latest})"
        ).fetchone()
        latest_row = conn.execute(f"SELECT concentration_per_l FROM ({latest}) ORDER BY id DESC LIMIT 1").fetchone()
    total = totals["total"]
    return {
        "total_samples": samples, "total_particles": total, "suspected_plastic": totals["suspected"],
        "suspected_percentage": round(totals["suspected"] * 100 / total, 2) if total else 0,
        "latest_concentration_per_l": latest_row["concentration_per_l"] if latest_row else None,
        "timeline": timeline, "class_distribution": dict(classes), "recent_samples": recent, "disclaimer": DISCLAIMER,
    }
