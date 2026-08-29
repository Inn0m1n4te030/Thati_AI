import pytest
from types import SimpleNamespace

from thati.clients import get_fraud_client, set_fraud_client
from thati.config import reset_settings
from thati.errors import ProviderError
from thati.live_client import GeminiFraudClient
from thati.schemas import FraudAssessment
from tests.test_analyze_image import PNG_BYTES
from tests.test_live_image import FAKE_FILE_NAME, FAKE_FILE_URI
from tests.test_schemas import SOURCE, _valid_assessment


def _fake_response(text: str = SOURCE) -> SimpleNamespace:
    return SimpleNamespace(
        parsed=FraudAssessment.model_validate(_valid_assessment(extracted_text=text))
    )


class _Http:
    def __init__(self) -> None:
        self.closed = False


class _Files:
    def __init__(self, http: _Http) -> None:
        self._http = http

    def upload(self, **_kwargs: object) -> SimpleNamespace:
        if self._http.closed:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        return SimpleNamespace(name=FAKE_FILE_NAME, uri=FAKE_FILE_URI)

    def delete(self, **_kwargs: object) -> None:
        return None


class _Models:
    def __init__(self, http: _Http) -> None:
        self._http = http

    def generate_content(self, **_kwargs: object) -> SimpleNamespace:
        if self._http.closed:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        return _fake_response()


class _ClosingSdk:
    """Mirrors google-genai: Client.__del__ closes httpx while Files/Models remain."""

    def __init__(self) -> None:
        self._http = _Http()
        self.files = _Files(self._http)
        self.models = _Models(self._http)

    def __del__(self) -> None:
        self._http.closed = True


def test_image_upload_survives_when_sdk_is_retained(tmp_path) -> None:
    path = tmp_path / "shot.png"
    path.write_bytes(PNG_BYTES)
    try:
        dropped_sdk = _ClosingSdk()
        dropped = GeminiFraudClient(
            model="gemini-3.7-flash",
            generate_content=dropped_sdk.models.generate_content,
            files_upload=dropped_sdk.files.upload,
            files_delete=dropped_sdk.files.delete,
        )
        dropped_sdk.__del__()
        with pytest.raises(ProviderError):
            dropped.analyze_image(path, "image/png")

        sdk = _ClosingSdk()
        retained = GeminiFraudClient(
            model="gemini-3.7-flash",
            generate_content=sdk.models.generate_content,
            files_upload=sdk.files.upload,
            files_delete=sdk.files.delete,
            sdk=sdk,
        )
        assessment = retained.analyze_image(path, "image/png")
        assert assessment.extracted_text == SOURCE
    finally:
        path.unlink(missing_ok=True)


def test_get_fraud_client_reuses_live_sdk(monkeypatch) -> None:
    builds: list[int] = []
    sentinel = object()

    def fake_build(_settings: object) -> object:
        builds.append(1)
        return sentinel

    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    reset_settings()
    set_fraud_client(None)
    monkeypatch.setattr("thati.live_client.build_live_client", fake_build)

    first = get_fraud_client()
    second = get_fraud_client()
    assert first is sentinel
    assert second is sentinel
    assert builds == [1]
    set_fraud_client(None)
