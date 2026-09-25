from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import analyze, calibration, device, export, ml, samples, settings, stats
from .config import config
from .db import initialize_database
from .ml.model import ensure_starter_model


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_directories()
    initialize_database()
    ensure_starter_model()
    yield


app = FastAPI(
    title="MicroPlast Screen API",
    version="1.0.0",
    description="Local visual screening for suspected microplastic particles. This does not provide chemical polymer identification.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-Sample-Id"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(samples.router)
app.include_router(analyze.router)
app.include_router(settings.router)
app.include_router(calibration.router)
app.include_router(ml.router)
app.include_router(export.router)
app.include_router(stats.router)
app.include_router(device.router)
app.mount("/", StaticFiles(directory=config.root_dir / "frontend", html=True), name="frontend")
