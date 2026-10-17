from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response

from ..db import database, utc_now
from ..schemas import SampleCreate, SampleUpdate
from ..storage import delete_assets
from .common import create_sample, require_sample, response_for_sample

router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.post("", status_code=201)
def add_sample(payload: SampleCreate):
    return create_sample(payload.model_dump())


@router.get("")
def list_samples(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort: Literal["created_at", "name", "suspected_plastic", "total_particles"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    sort_columns = {"created_at": "s.created_at", "name": "s.name", "suspected_plastic": "COALESCE(a.suspected_plastic, 0)", "total_particles": "COALESCE(a.total_particles, 0)"}
    # ILIKE: Postgres' LIKE is case-sensitive, and the search box should not be.
    where = "WHERE s.name ILIKE %s OR COALESCE(s.location, '') ILIKE %s" if search else ""
    parameters = [f"%{search}%", f"%{search}%"] if search else []
    latest_join = "LEFT JOIN analyses a ON a.id = (SELECT id FROM analyses WHERE sample_id = s.id ORDER BY id DESC LIMIT 1)"
    with database() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS count FROM samples s {where}", parameters).fetchone()["count"]
        rows = conn.execute(
            f"""SELECT s.*, a.id AS analysis_id, a.suspected_plastic, a.total_particles, a.concentration_per_l,
                       a.annotated_path, a.created_at AS analysis_created_at
                FROM samples s {latest_join} {where}
                ORDER BY {sort_columns[sort]} {order.upper()} LIMIT %s OFFSET %s""",
            [*parameters, per_page, (page - 1) * per_page],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "page": page, "per_page": per_page}


@router.get("/{sample_id}")
def get_sample(sample_id: int):
    return response_for_sample(sample_id)


@router.patch("/{sample_id}")
def update_sample(sample_id: int, payload: SampleUpdate):
    require_sample(sample_id)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return require_sample(sample_id)
    columns = ", ".join(f"{name} = %s" for name in values)
    with database() as conn:
        conn.execute(f"UPDATE samples SET {columns}, updated_at = %s WHERE id = %s", [*values.values(), utc_now(), sample_id])
        row = conn.execute("SELECT * FROM samples WHERE id = %s", (sample_id,)).fetchone()
    return dict(row)


@router.delete("/{sample_id}", status_code=204)
def delete_sample(sample_id: int):
    require_sample(sample_id)
    with database() as conn:
        paths = conn.execute("SELECT original_path, annotated_path, mask_path FROM analyses WHERE sample_id = %s", (sample_id,)).fetchall()
        conn.execute("DELETE FROM samples WHERE id = %s", (sample_id,))
    delete_assets([path for row in paths for path in row.values()])
    return Response(status_code=204)
