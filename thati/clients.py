"""Fraud client factory. Mock mode does not import the Gemini SDK."""

from __future__ import annotations

from typing import Protocol

from thati.config import get_settings
from thati.mock_client import MockFraudClient
from thati.schemas import FraudAssessment

_override: FraudClient | None = None


class FraudClient(Protocol):
    def analyze_text(self, text: str) -> FraudAssessment: ...


def set_fraud_client(client: FraudClient | None) -> None:
    global _override
    _override = client


def get_fraud_client() -> FraudClient:
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.app_mode == "mock":
        return MockFraudClient()
    from thati.live_client import build_live_client

    return build_live_client(settings)
