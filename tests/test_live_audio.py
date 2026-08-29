import base64
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from thati.clients import set_fraud_client
from thati.config import reset_settings
from thati.live_client import (
    GeminiFraudClient,
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_VOCABULARY,
    TRANSCRIBE_ONLY_PROMPT,
    audio_inline_input,
    audio_interaction_input,
    live_transcription_config,
    wrap_untrusted_message,
)
from thati.mock_client import SYNTHETIC_VOICE_TRANSCRIPT
from thati.schemas import FraudAssessment
from tests.test_analyze_audio import wav_bytes
from tests.test_schemas import _valid_assessment

FAKE_FILE_URI = "https://generativelanguage.googleapis.com/v1beta/files/thati-audio"


def test_transcription_request_uses_burmese_smart_config() -> None:
    config = live_transcription_config()["transcription_config"]
    assert config["language_codes"][0] == "my-MM"
    assert config["language_codes"] == TRANSCRIPTION_LANGUAGE_CODES
    assert "en-US" in config["language_codes"]
    assert config["mode"] == {"type": "smart"}
    for term in ("KBZPay", "Wave Money", "OTP", "PIN", "AYA", "CVV", "အကောင့်"):
        assert term in config["custom_vocabulary"]
        assert term in TRANSCRIPTION_VOCABULARY
    assert "မြန်မာ" in TRANSCRIBE_ONLY_PROMPT
    assert "Burmese" in TRANSCRIBE_ONLY_PROMPT
    inline = audio_inline_input(b"abc", "audio/mp4")
    assert inline == [
        {
            "type": "audio",
            "mime_type": "audio/m4a",
            "data": base64.b64encode(b"abc").decode("ascii"),
        }
    ]
    assert audio_interaction_input(FAKE_FILE_URI, "audio/mp4") == [
        {"type": "audio", "uri": FAKE_FILE_URI, "mime_type": "audio/m4a"}
    ]


def test_live_audio_transcribes_inline_then_analyzes_text() -> None:
    interactions: list[dict[str, object]] = []
    generates: list[dict[str, object]] = []
    data = wav_bytes()

    def fake_interaction(*, model: str, input: object, generation_config: dict[str, object]) -> SimpleNamespace:
        interactions.append(
            {"model": model, "input": input, "generation_config": generation_config}
        )
        return SimpleNamespace(output_text=SYNTHETIC_VOICE_TRANSCRIPT)

    def fake_generate(*, model: str, contents: object, config: dict[str, object]) -> SimpleNamespace:
        generates.append({"model": model, "contents": contents, "config": config})
        return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment()))

    live = GeminiFraudClient(
        model="gemini-3.7-flash",
        transcription_model="gemini-3.5-transcribe",
        generate_content=fake_generate,
        create_interaction=fake_interaction,
    )
    path = Path("clip.wav")
    path.write_bytes(data)
    try:
        assessment = live.analyze_audio(path, "audio/wav")
    finally:
        path.unlink(missing_ok=True)

    assert len(interactions) == 1
    transcribe = interactions[0]
    assert transcribe["model"] == "gemini-3.5-transcribe"
    assert transcribe["input"] == audio_inline_input(data, "audio/wav")
    cfg = transcribe["generation_config"]["transcription_config"]
    assert cfg["language_codes"][0] == "my-MM"
    assert cfg["mode"] == {"type": "smart"}
    assert generates[0]["model"] == "gemini-3.7-flash"
    assert generates[0]["contents"] == wrap_untrusted_message(SYNTHETIC_VOICE_TRANSCRIPT)
    assert assessment.extracted_text == SYNTHETIC_VOICE_TRANSCRIPT


def test_empty_interactions_transcript_falls_back_to_understanding_model() -> None:
    generates: list[object] = []
    data = wav_bytes()

    def empty_interaction(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(output_text="   ", text=None, parsed=None, steps=[])

    def fake_generate(*, model: str, contents: object, config: object = None) -> SimpleNamespace:
        generates.append(contents)
        if isinstance(contents, list):
            return SimpleNamespace(text=SYNTHETIC_VOICE_TRANSCRIPT, parsed=None, output_text=None)
        return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment()))

    live = GeminiFraudClient(
        model="gemini-3.7-flash",
        transcription_model="gemini-3.5-transcribe",
        generate_content=fake_generate,
        create_interaction=empty_interaction,
    )
    path = Path("clip.wav")
    path.write_bytes(data)
    try:
        assessment = live.analyze_audio(path, "audio/wav")
    finally:
        path.unlink(missing_ok=True)

    assert generates[0][0]["inline_data"]["mime_type"] == "audio/wav"
    assert generates[0][0]["inline_data"]["data"] == base64.b64encode(data).decode("ascii")
    assert "မြန်မာ" in generates[0][1]
    assert assessment.extracted_text == SYNTHETIC_VOICE_TRANSCRIPT


def test_live_audio_http_cleanup_on_success_and_failure(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-should-not-leak")
    reset_settings()

    def fake_interaction(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(output_text=SYNTHETIC_VOICE_TRANSCRIPT)

    def fake_generate(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment()))

    set_fraud_client(
        GeminiFraudClient(
            model="gemini-3.7-flash",
            transcription_model="gemini-3.5-transcribe",
            generate_content=fake_generate,
            create_interaction=fake_interaction,
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

    def boom(**_kwargs: object) -> SimpleNamespace:
        raise TimeoutError("generativelanguage.googleapis.com timed out")

    set_fraud_client(
        GeminiFraudClient(
            model="gemini-3.7-flash",
            transcription_model="gemini-3.5-transcribe",
            generate_content=boom,
            create_interaction=boom,
        )
    )
    failed = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    assert failed.status_code == 502
    assert failed.json() == {"error": "provider_error"}
    assert "Traceback" not in failed.text
    assert "secret-should-not-leak" not in failed.text
