from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import database
from ..ml.model import model_status, train_model
from ..schemas import ParticleUpdate, TrainRequest

router = APIRouter(prefix="/api", tags=["machine learning"])


@router.get("/ml/status")
def ml_status():
    return model_status()


@router.post("/ml/train")
def retrain_model(payload: TrainRequest):
    with database() as conn:
        verified = [dict(row) for row in conn.execute("SELECT * FROM particles WHERE user_verified_class IS NOT NULL")]
    if not payload.include_synthetic and len({item["user_verified_class"] for item in verified}) < 2:
        raise HTTPException(status_code=422, detail="At least two verified classes are required when synthetic data is excluded")
    return train_model(verified if payload.include_verified_particles else [], payload.include_synthetic)


@router.patch("/particles/{particle_id}")
def correct_particle(particle_id: int, payload: ParticleUpdate):
    with database() as conn:
        exists = conn.execute("SELECT id FROM particles WHERE id = ?", (particle_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Particle not found")
        conn.execute("UPDATE particles SET user_verified_class = ? WHERE id = ?", (payload.user_verified_class, particle_id))
        item = conn.execute("SELECT * FROM particles WHERE id = ?", (particle_id,)).fetchone()
    return dict(item)
