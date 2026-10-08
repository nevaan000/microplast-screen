from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..config import config
from ..db import database, utc_now

router = APIRouter(prefix="/api/auth", tags=["authentication"])

COOKIE_NAME = "mps_session"
MAX_FAILURES_PER_WINDOW = 8
FAILURE_WINDOW_SECONDS = 600
_failures: dict[str, list[float]] = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    recent = [stamp for stamp in _failures.get(ip, []) if now - stamp < FAILURE_WINDOW_SECONDS]
    _failures[ip] = recent
    return len(recent) >= MAX_FAILURES_PER_WINDOW


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


def session_user(request: Request) -> str | None:
    if not config.auth_enabled:
        return None
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    with database() as conn:
        row = conn.execute("SELECT expires_at FROM sessions WHERE token = ?", (token,)).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= utc_now():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
    return config.admin_user


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    if not config.auth_enabled:
        raise HTTPException(status_code=400, detail="This server runs without a login; set ADMIN_PASSWORD to enable one")
    ip = _client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again in a few minutes.")
    matches = secrets.compare_digest(payload.username, config.admin_user) and secrets.compare_digest(
        payload.password, config.admin_password
    )
    if not matches:
        _failures.setdefault(ip, []).append(time.monotonic())
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    _failures.pop(ip, None)
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=config.session_hours)).isoformat()
    with database() as conn:
        conn.execute(
            "INSERT INTO sessions(token, created_at, expires_at) VALUES (?, ?, ?)",
            (token, utc_now(), expires),
        )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=config.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )
    return {"user": config.admin_user}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with database() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "signed out"}


@router.get("/me")
def me(request: Request):
    user = session_user(request)
    authenticated = user is not None or not config.auth_enabled
    return {"auth_enabled": config.auth_enabled, "authenticated": authenticated, "user": user if authenticated else None}
