"""Fraud client factory. Mock mode must not import external SDKs."""

from thati.config import get_settings
from thati.mock_client import MockFraudClient


def get_fraud_client() -> MockFraudClient:
    settings = get_settings()
    if settings.app_mode != "mock":
        raise RuntimeError("live_mode_unavailable")
    return MockFraudClient()
