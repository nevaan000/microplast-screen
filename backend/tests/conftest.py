import shutil

import pytest

from backend.app.config import config
from backend.app.db import initialize_database


@pytest.fixture(autouse=True)
def database_ready():
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
