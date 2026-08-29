"""Voice analysis is optional and must not change text or image flows."""

from __future__ import annotations

import struct
from pathlib import Path

from fastapi.testclient import TestClient

from thati.audio import AUDIO_MAX_BYTES
from thati.mock_client import SYNTHETIC_SCREENSHOT_TEXT, SYNTHETIC_VOICE_TRANSCRIPT
from tests.test_analyze_image import PNG_BYTES
from tests.test_analyze_text import OTP_PHISHING


def wav_bytes() -> bytes:
    pcm = b"\x00\x00" * 32
    fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<I", 16)
        + fmt
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 32


def test_public_page_enables_audio_tab(client: TestClient) -> None:
    html = client.get("/").text
    voice = html.split('id="tab-voice"', 1)[1].split("</button>", 1)[0]
    assert "disabled" not in voice
    assert 'data-panel="panel-audio"' in html
    assert 'id="record-start"' in html
    assert 'id="audio-dropzone"' in html


def test_app_js_audio_states_without_innerhtml() -> None:
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "AUDIO_MAX_BYTES = 25 * 1024 * 1024" in script
    assert "/api/analyze/audio" in script
    assert "MediaRecorder" in script
    assert "NotAllowedError" in script
    assert "စာသားမှတ်တမ်း" in script


def test_mock_wav_returns_deterministic_transcript(client: TestClient) -> None:
    first = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    second = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["source_type"] == "voice"
    assert body["transcript"] == SYNTHETIC_VOICE_TRANSCRIPT
    assert body["assessment"]["extracted_text"] == SYNTHETIC_VOICE_TRANSCRIPT
    assert body["assessment"] == second.json()["assessment"]
    assert "OTP" in body["transcript"]


def test_rejects_unsupported_audio_type(client: TestClient) -> None:
    response = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "unsupported_audio_type"}


def test_rejects_audio_over_25mb(client: TestClient) -> None:
    payload = wav_bytes()[:12] + b"\x00" * (AUDIO_MAX_BYTES)
    response = client.post(
        "/api/analyze/audio",
        files={"file": ("huge.wav", payload, "audio/wav")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "audio_too_large"}


def test_webm_is_converted_and_temps_are_removed(client: TestClient, monkeypatch) -> None:
    created: list[Path] = []

    def fake_convert(source: Path) -> Path:
        dest = source.with_name(source.name + "-16k.wav")
        dest.write_bytes(wav_bytes())
        created.append(source)
        created.append(dest)
        return dest

    monkeypatch.setattr("thati.routers.analyze.prepare_provider_audio", lambda path, mime: (fake_convert(path), "audio/wav"))
    response = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.webm", WEBM_BYTES, "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["source_type"] == "voice"
    assert created
    assert all(not path.exists() for path in created)


def test_text_and_image_still_work_after_audio(client: TestClient) -> None:
    audio = client.post(
        "/api/analyze/audio",
        files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
    )
    assert audio.status_code == 200
    text = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert text.status_code == 200
    assert text.json()["source_type"] == "text"
    assert text.json()["assessment"]["risk_level"] == "critical"
    image = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert image.status_code == 200
    assert image.json()["source_type"] == "screenshot"
    assert image.json()["assessment"]["extracted_text"] == SYNTHETIC_SCREENSHOT_TEXT
