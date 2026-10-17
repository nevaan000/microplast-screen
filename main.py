"""Vercel's Python runtime loads the `app` variable from a root-level entrypoint.

Locally the same application runs with `python -m uvicorn backend.app.main:app`.
"""
from backend.app.main import app

__all__ = ["app"]
