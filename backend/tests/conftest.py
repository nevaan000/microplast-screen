from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

# config resolves DATA_DIR when backend.app.config is first imported, so the test
# data directory must be set before that import. Without this isolation the
# clean_data fixture deletes analysis images from the real data directory.
# It must stay inside the project root because stored image paths are relative to it.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DATA_DIR = PROJECT_ROOT / f".pytest-data-{uuid.uuid4().hex[:8]}"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = TEST_DATA_DIR.name

from backend.app.config import config  # noqa: E402
from backend.app.db import initialize_database  # noqa: E402


@pytest.fixture(autouse=True)
def database_ready():
    config.ensure_directories()
    initialize_database()
    yield


@pytest.fixture
def clean_data():
    for directory in (config.raw_dir, config.processed_dir, config.masks_dir, config.exports_dir):
        for path in directory.glob("*"):
            if path.name != ".gitkeep":
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    yield


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
