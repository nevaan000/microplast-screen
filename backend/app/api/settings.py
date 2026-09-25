from __future__ import annotations

from fastapi import APIRouter

from ..db import get_settings, reset_settings, update_settings
from ..schemas import SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings():
    return {"settings": get_settings()}


@router.put("")
def save_settings(payload: SettingsUpdate):
    return {"settings": update_settings(payload.values)}


@router.post("/reset")
def restore_default_settings():
    return {"settings": reset_settings()}
