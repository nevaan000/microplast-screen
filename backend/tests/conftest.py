from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

# config resolves DATA_DIR when backend.app.config is first imported, so the test
# data directory must be set before that import. Without this isolation the
# clean_data fixture deletes analysis images from the real data directory.
# It deliberately lives OUTSIDE the project root: a container deployment mounts
# its volume at /data, and stored asset paths must stay valid there.
TEST_DATA_DIR = Path(tempfile.gettempdir()) / f"microplast-pytest-{uuid.uuid4().hex[:8]}"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(TEST_DATA_DIR)

from backend.app.config import config  # noqa: E402
from backend.app.db import initialize_database  # noqa: E402

assert config.data_dir.resolve() == TEST_DATA_DIR.resolve(), "DATA_DIR outside the project root was not honoured"


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
