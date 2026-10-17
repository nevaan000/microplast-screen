from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

# config resolves DATA_DIR and DATABASE_URL when backend.app.config is first
# imported, so both must be set before that import.
TEST_DATA_DIR = Path(tempfile.gettempdir()) / f"microplast-pytest-{uuid.uuid4().hex[:8]}"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(TEST_DATA_DIR)

# Assets stay on disk: a Blob store would spend real quota and need network
# access on every run.
os.environ["ASSET_BACKEND"] = "local"

# Deliberately NOT a fallback to DATABASE_URL. The fixture below truncates every
# table, so an inherited production connection string would destroy real data.
# `docker run -d --name mps-postgres -e POSTGRES_USER=microplast \
#   -e POSTGRES_PASSWORD=microplast_dev_only -e POSTGRES_DB=microplast \
#   -p 5433:5432 postgres:17-alpine` provides the default.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or (
    "postgresql://microplast:microplast_dev_only@127.0.0.1:5433/microplast"
)

from backend.app.config import config  # noqa: E402
from backend.app.db import database, initialize_database  # noqa: E402

assert config.data_dir.resolve() == TEST_DATA_DIR.resolve(), "DATA_DIR outside the project root was not honoured"
assert not config.blob_enabled, "ASSET_BACKEND=local did not disable Vercel Blob"

TRUNCATED = "samples, calibrations, sessions"


@pytest.fixture(autouse=True)
def database_ready():
    config.ensure_directories()
    initialize_database()
    # CASCADE reaches analyses and particles; RESTART IDENTITY keeps generated
    # ids predictable across tests. settings is left alone on purpose.
    with database() as conn:
        conn.execute(f"TRUNCATE {TRUNCATED} RESTART IDENTITY CASCADE")
    yield


@pytest.fixture
def clean_data():
    # The trained classifier is left in place: wiping it would make every test
    # that starts the app retrain the starter model from scratch.
    for path in TEST_DATA_DIR.rglob("*"):
        if path.is_file() and "models" not in path.relative_to(TEST_DATA_DIR).parts:
            path.unlink()
    yield


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
