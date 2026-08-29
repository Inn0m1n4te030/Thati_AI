from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from thati.clients import set_fraud_client
from thati.config import get_settings, reset_settings
from thati.main import app
from thati.rate_limit import analyze_limiter


def _restore_limiter() -> None:
    settings = get_settings()
    analyze_limiter.configure(
        max_requests=settings.analyze_rate_limit,
        window_seconds=settings.analyze_rate_window_seconds,
    )
    analyze_limiter.reset()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "thati.db"))
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    reset_settings()
    _restore_limiter()
    set_fraud_client(None)
    with TestClient(app) as test_client:
        yield test_client
    set_fraud_client(None)
    app.dependency_overrides.clear()
    _restore_limiter()
    reset_settings()
