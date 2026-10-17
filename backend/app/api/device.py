from __future__ import annotations

import hmac
import re
import time
import uuid
from typing import Any

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..config import config
from ..db import get_settings
from ..schemas import DeviceCaptureRequest, DeviceLedRequest
from ..storage import AssetNotFound, delete_assets, list_assets, put_asset, read_asset
from .common import analysis_slot, decode_image, persist_analysis, require_sample
from .analyze import _active_mm_per_pixel

router = APIRouter(prefix="/api/device", tags=["ESP32-CAM device"])


def _require_api_key(key: str | None) -> None:
    if not key or not hmac.compare_digest(key, config.device_api_key):
        raise HTTPException(status_code=401, detail="A valid X-API-Key is required")


def _host(value: str | None) -> str:
    host = (value or get_settings().get("esp32_ip") or "").strip()
    if not host:
        raise HTTPException(status_code=409, detail="ESP32 IP or hostname is not configured")
    if any(character in host for character in "/?@# \\ ") or host.startswith(("http:", "https:")):
        raise HTTPException(status_code=422, detail="ESP32 host must be a hostname, IP address, or optional port")
    return host


def _url(host: str, endpoint: str) -> str:
    return f"http://{host}{endpoint}"


def _camera_defaults() -> dict[str, Any]:
    settings = get_settings()
    params = {"framesize": settings.get("camera_framesize"), "quality": settings.get("camera_quality")}
    return {key: value for key, value in params.items() if value not in (None, "")}


def _store_device_frame(sample_id: int, content: bytes, content_type: str | None, session: str, complete: bool, volume_ml: float | None) -> dict[str, Any]:
    frame = decode_image(content, content_type)
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise HTTPException(status_code=500, detail="Could not store uploaded device frame")
    prefix = f"raw/session-{sample_id}-{session}-"
    # Frames land in shared storage, not on a local disk: consecutive uploads from
    # one camera can be served by different instances. The timestamp keeps the
    # lexicographic listing in capture order.
    put_asset(f"{prefix}{time.time_ns():020d}.jpg", encoded.tobytes(), "image/jpeg")
    if not complete:
        return {"stored": True, "capture_session": session, "analysis": None}
    # Storing a single frame is cheap and stays outside the slot, so a camera
    # mid-session is never made to wait out an unrelated analysis. Only the final
    # frame, which loads the whole session into memory, is queued.
    pathnames = list_assets(prefix)
    with analysis_slot():
        frames = []
        for pathname in pathnames:
            try:
                stored = read_asset(pathname)
            except AssetNotFound:
                continue
            decoded = cv2.imdecode(np.frombuffer(stored, dtype=np.uint8), cv2.IMREAD_COLOR)
            if decoded is not None:
                frames.append(decoded)
        if not frames:
            raise HTTPException(status_code=400, detail="No decodable frames were available for the completed capture session")
        analysis = persist_analysis(sample_id, frames, volume_ml, get_settings(), _active_mm_per_pixel())
    delete_assets(pathnames)
    return {"stored": True, "capture_session": session, "analysis": analysis}


@router.post("/upload", status_code=201)
async def upload_from_device(
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_sample_id: int | None = Header(default=None),
    x_capture_session: str | None = Header(default=None),
    x_capture_complete: str | None = Header(default="true"),
):
    _require_api_key(x_api_key)
    if x_sample_id is None:
        raise HTTPException(status_code=422, detail="X-Sample-Id header is required")
    sample = require_sample(x_sample_id)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/"):
        form = await request.form()
        item = form.get("image") or form.get("file")
        if item is None or not hasattr(item, "read"):
            raise HTTPException(status_code=400, detail="Multipart device upload requires an image or file field")
        content = await item.read()
        image_content_type = getattr(item, "content_type", None)
    else:
        content = await request.body()
        image_content_type = content_type
    session = re.sub(r"[^A-Za-z0-9_-]", "", x_capture_session or uuid.uuid4().hex)[:64]
    if not session:
        raise HTTPException(status_code=422, detail="Invalid capture session identifier")
    complete = x_capture_complete.lower() in {"1", "true", "yes", "final"}
    # Decoding, frame stacking and the analysis all run off the event loop: a
    # queued analysis must not freeze health checks for other requests.
    result = await run_in_threadpool(
        _store_device_frame, x_sample_id, content, image_content_type, session, complete, sample.get("volume_ml")
    )
    if result.get("analysis") is not None:
        result["sample"] = sample
    return result


@router.post("/capture", status_code=201)
def pull_capture(payload: DeviceCaptureRequest, x_api_key: str | None = Header(default=None)):
    _require_api_key(x_api_key)
    sample = require_sample(payload.sample_id)
    host = _host(payload.esp32_ip)
    captures = []
    try:
        with httpx.Client(timeout=8.0) as client:
            defaults = _camera_defaults()
            if defaults:
                client.get(_url(host, "/config"), params=defaults).raise_for_status()
            for _ in range(payload.frames):
                response = client.get(_url(host, "/capture"))
                response.raise_for_status()
                captures.append((response.content, response.headers.get("content-type")))
    except (httpx.HTTPError, HTTPException) as error:
        detail = error.detail if isinstance(error, HTTPException) else f"Could not capture from ESP32-CAM: {error}"
        raise HTTPException(status_code=502, detail=detail) from error
    # The camera round-trips stay outside the slot so a slow or offline camera
    # cannot block an unrelated capture from being analysed.
    with analysis_slot():
        frames = [decode_image(content, content_type) for content, content_type in captures]
        analysis = persist_analysis(payload.sample_id, frames, sample.get("volume_ml"), get_settings(), _active_mm_per_pixel())
    return {"sample": sample, "analysis": analysis}


@router.get("/status")
def device_status(esp32_ip: str | None = None):
    try:
        host = _host(esp32_ip)
        with httpx.Client(timeout=3.0) as client:
            response = client.get(_url(host, "/status"))
            response.raise_for_status()
            info = response.json()
        return {"online": True, "host": host, **info}
    except (HTTPException, httpx.HTTPError, ValueError) as error:
        if isinstance(error, HTTPException) and error.status_code == 409:
            return {"online": False, "detail": error.detail}
        return {"online": False, "detail": str(error)}


@router.post("/led")
def set_led(payload: DeviceLedRequest, x_api_key: str | None = Header(default=None)):
    _require_api_key(x_api_key)
    host = _host(None)
    try:
        response = httpx.get(_url(host, "/led"), params={"state": payload.state, "level": payload.level}, timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Could not update ESP32 LED: {error}") from error
    return {"ok": True, "device_response": response.json() if "json" in response.headers.get("content-type", "") else response.text}


@router.post("/config")
def configure_camera(payload: dict[str, Any], x_api_key: str | None = Header(default=None)):
    _require_api_key(x_api_key)
    allowed = {"framesize", "quality", "lock_exposure"}
    params = {key: value for key, value in payload.items() if key in allowed}
    if not params:
        raise HTTPException(status_code=422, detail="Provide framesize, quality, or lock_exposure")
    try:
        response = httpx.get(_url(_host(None), "/config"), params=params, timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Could not configure ESP32 camera: {error}") from error
    return response.json() if "json" in response.headers.get("content-type", "") else {"ok": True}


@router.get("/stream-frame")
def stream_frame(esp32_ip: str | None = None):
    try:
        response = httpx.get(_url(_host(esp32_ip), "/capture"), timeout=5.0)
        response.raise_for_status()
        frame = decode_image(response.content, response.headers.get("content-type"))
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("Could not encode camera frame")
        return Response(encoded.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except (HTTPException, httpx.HTTPError, ValueError) as error:
        detail = error.detail if isinstance(error, HTTPException) else f"Could not read ESP32 preview: {error}"
        raise HTTPException(status_code=502, detail=detail) from error
