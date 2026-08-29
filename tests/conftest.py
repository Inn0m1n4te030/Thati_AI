from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from thati.config import reset_settings
from thati.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "thati.db"))
    reset_settings()
    with TestClient(app) as test_client:
        yield test_client
    reset_settings()
