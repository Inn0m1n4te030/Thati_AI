from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from thati.clients import set_fraud_client
from thati.config import reset_settings
from thati.live_client import (
    GeminiFraudClient,
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_VOCABULARY,
    audio_generate_contents,
    live_transcription_config,
    wrap_untrusted_message,
)
from thati.mock_client import SYNTHETIC_VOICE_TRANSCRIPT
from thati.schemas import FraudAssessment
from tests.test_analyze_audio import wav_bytes
from tests.test_schemas import _valid_assessment

FAKE_FILE_URI = "https://generativelanguage.googleapis.com/v1beta/files/thati-audio"
FAKE_FILE_NAME = "files/thati-audio"


def test_transcription_request_schema_has_language_hints_and_smart_mode() -> None:
    config = live_transcription_config()["audio_transcription_config"]
    assert config["language_codes"] == ["my-MM", "en-US"]
    assert config["language_hints"]["language_codes"] == TRANSCRIPTION_LANGUAGE_CODES
    assert config["mode"] == "SMART"
    for term in ("KBZPay", "Wave Money", "OTP", "PIN", "account", "transfer"):
        assert term in config["custom_vocabulary"]
        assert term in TRANSCRIPTION_VOCABULARY
    contents = audio_generate_contents(FAKE_FILE_URI, "audio/wav")
    assert contents[0]["file_data"]["file_uri"] == FAKE_FILE_URI
    assert contents[0]["file_data"]["mime_type"] == "audio/wav"


def test_live_audio_transcribes_then_analyzes_text_and_deletes_files() -> None:
    calls: list[dict[str, object]] = []
    deleted: list[str] = []

    def fake_upload(*, file: str, config: dict[str, str] | None = None) -> SimpleNamespace:
        assert Path(file).exists()
        assert config == {"mime_type": "audio/wav"}
        return SimpleNamespace(name=FAKE_FILE_NAME, uri=FAKE_FILE_URI)

    def fake_delete(*, name: str, config: object = None) -> None:
        deleted.append(name)

    def fake_generate(*, model: str, contents: object, config: dict[str, object]) -> SimpleNamespace:
        calls.append({"model": model, "contents": contents, "config": config})
        if model == "gemini-3.5-transcribe":
            return SimpleNamespace(text=SYNTHETIC_VOICE_TRANSCRIPT, parsed=None)
        return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment()))

    live = GeminiFraudClient(
        model="gemini-3.7-flash",
        transcription_model="gemini-3.5-transcribe",
        generate_content=fake_generate,
        files_upload=fake_upload,
        files_delete=fake_delete,
    )
    path = Path("clip.wav")
    path.write_bytes(wav_bytes())
    try:
        assessment = live.analyze_audio(path, "audio/wav")
    finally:
        path.unlink(missing_ok=True)

    assert [item["model"] for item in calls] == [
        "gemini-3.5-transcribe",
        "gemini-3.7-flash",
    ]
    transcribe = calls[0]
    assert transcribe["contents"] == audio_generate_contents(FAKE_FILE_URI, "audio/wav")
    cfg = transcribe["config"]["audio_transcription_config"]
    assert cfg["language_codes"] == ["my-MM", "en-US"]
    assert cfg["mode"] == "SMART"
    assert "KBZPay" in cfg["custom_vocabulary"]
    analyze = calls[1]
    assert analyze["contents"] == wrap_untrusted_message(SYNTHETIC_VOICE_TRANSCRIPT)
    assert assessment.extracted_text == SYNTHETIC_VOICE_TRANSCRIPT
    assert deleted == [FAKE_FILE_NAME]


def test_live_audio_http_cleanup_on_success_and_failure(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-should-not-leak")
    reset_settings()
    deleted: list[str] = []
    local_paths: list[str] = []

    def fake_upload(*, file: str, config: dict[str, str] | None = None) -> SimpleNamespace:
        local_paths.append(file)
        assert Path(file).exists()
        return SimpleNamespace(name=FAKE_FILE_NAME, uri=FAKE_FILE_URI)

    def fake_delete(*, name: str, config: object = None) -> None:
        deleted.append(name)

    def fake_generate(*, model: str, contents: object, config: dict[str, object]) -> SimpleNamespace:
        if model == "gemini-3.5-transcribe":
            return SimpleNamespace(text=SYNTHETIC_VOICE_TRANSCRIPT, parsed=None)
        return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment()))

    set_fraud_client(
        GeminiFraudClient(
            model="gemini-3.7-flash",
            transcription_model="gemini-3.5-transcribe",
            generate_content=fake_generate,
            files_upload=fake_upload,
            files_delete=fake_delete,
        )
    )
    ok = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    assert ok.status_code == 200
    assert ok.json()["source_type"] == "voice"
    assert ok.json()["transcript"] == SYNTHETIC_VOICE_TRANSCRIPT
    assert "secret-should-not-leak" not in ok.text
    assert deleted == [FAKE_FILE_NAME]
    assert local_paths
    assert all(not Path(path).exists() for path in local_paths)

    deleted.clear()
    local_paths.clear()

    def boom(**_kwargs: object) -> SimpleNamespace:
        raise TimeoutError("generativelanguage.googleapis.com timed out")

    set_fraud_client(
        GeminiFraudClient(
            model="gemini-3.7-flash",
            transcription_model="gemini-3.5-transcribe",
            generate_content=boom,
            files_upload=fake_upload,
            files_delete=fake_delete,
        )
    )
    failed = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    assert failed.status_code == 502
    assert failed.json() == {"error": "provider_error"}
    assert deleted == [FAKE_FILE_NAME]
    assert local_paths
    assert all(not Path(path).exists() for path in local_paths)
    assert "Traceback" not in failed.text
