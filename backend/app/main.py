from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from .api import analyze, auth, calibration, device, export, ml, samples, settings, stats
from .config import config
from .db import initialize_database
from .ml.model import ensure_starter_model


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_directories()
    initialize_database()
    ensure_starter_model()
    if not config.auth_enabled:
        print("WARNING: ADMIN_PASSWORD is not set, so the dashboard has no login. "
              "Fine on localhost/LAN; set it before exposing this server to the internet.")
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

# The ESP32 authenticates with its device API key and cannot hold a browser
# session cookie, so the upload endpoint stays outside the session gate.
UNAUTHENTICATED_API = {"/api/health", "/api/auth/login", "/api/auth/me", "/api/auth/logout", "/api/device/upload"}


@app.middleware("http")
async def require_session(request: Request, call_next):
    path = request.scope["path"]
    protected = path.startswith("/api/") or path in {"/docs", "/redoc", "/openapi.json"}
    if config.auth_enabled and protected and path not in UNAUTHENTICATED_API and auth.session_user(request) is None:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(samples.router)
app.include_router(analyze.router)
app.include_router(settings.router)
app.include_router(calibration.router)
app.include_router(ml.router)
app.include_router(export.router)
app.include_router(stats.router)
app.include_router(device.router)
app.mount("/", StaticFiles(directory=config.root_dir / "frontend", html=True), name="frontend")
