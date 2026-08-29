"""Fraud client factory. Mock mode does not import the Gemini SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from thati.config import get_settings
from thati.mock_client import MockFraudClient
from thati.schemas import FraudAssessment

_override: FraudClient | None = None
_live_client: FraudClient | None = None


class FraudClient(Protocol):
    def analyze_text(self, text: str) -> FraudAssessment: ...

    def analyze_image(self, image_path: Path, mime_type: str) -> FraudAssessment: ...

    def analyze_audio(self, audio_path: Path, mime_type: str) -> FraudAssessment: ...


def set_fraud_client(client: FraudClient | None) -> None:
    global _override, _live_client
    _override = client
    if client is None:
        _live_client = None


def get_fraud_client() -> FraudClient:
    global _live_client
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.app_mode == "mock":
        return MockFraudClient()
    if _live_client is None:
        from thati.live_client import build_live_client

        _live_client = build_live_client(settings)
    return _live_client
