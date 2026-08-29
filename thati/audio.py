"""Audio upload checks, browser-WebM conversion, and private temp files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

AUDIO_MAX_BYTES = 25 * 1024 * 1024

ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "application/ogg",
    "audio/flac",
    "audio/x-flac",
    "audio/webm",
    "video/webm",
}

_NATIVE_PROVIDER_TYPES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "audio/flac",
}

_SNIFF_TO_MIME = (
    (b"RIFF", "audio/wav"),
    (b"ID3", "audio/mpeg"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"\x1a\x45\xdf\xa3", "audio/webm"),
)


class AudioValidationError(ValueError):
    """User-facing audio rejection; ``str(exc)`` is a stable error code."""


def _canonical_mime(declared: str) -> str:
    raw = (declared or "").split(";", 1)[0].strip().lower()
    aliases = {
        "audio/wave": "audio/wav",
        "audio/x-wav": "audio/wav",
        "audio/mp3": "audio/mpeg",
        "audio/x-m4a": "audio/m4a",
        "audio/aac": "audio/m4a",
        "application/ogg": "audio/ogg",
        "audio/x-flac": "audio/flac",
        "video/webm": "audio/webm",
    }
    return aliases.get(raw, raw)


def sniff_audio_mime(header: bytes) -> str | None:
    if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
        return "audio/wav"
    if len(header) >= 2 and header[0] == 0xFF and header[1] in {0xF3, 0xFB, 0xF2}:
        return "audio/mpeg"
    if header[4:8] == b"ftyp":
        return "audio/mp4"
    for magic, mime in _SNIFF_TO_MIME:
        if header.startswith(magic):
            return mime
    return None


CANONICAL_ALLOWED = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "audio/flac",
    "audio/webm",
}


def _compatible(sniffed: str, declared: str) -> bool:
    if sniffed == declared:
        return True
    families = (
        {"audio/wav"},
        {"audio/mpeg"},
        {"audio/mp4", "audio/m4a"},
        {"audio/ogg"},
        {"audio/flac"},
        {"audio/webm"},
    )
    return any({sniffed, declared} <= family for family in families)


def detect_audio_mime(header: bytes, declared_type: str | None) -> str:
    sniffed = sniff_audio_mime(header)
    declared = _canonical_mime(declared_type or "")
    if declared in {"", "application/octet-stream"}:
        if sniffed is None:
            raise AudioValidationError("unsupported_audio_type")
        return sniffed
    if declared not in CANONICAL_ALLOWED:
        raise AudioValidationError("unsupported_audio_type")
    if sniffed and not _compatible(sniffed, declared):
        raise AudioValidationError("unsupported_audio_type")
    return declared


def read_audio_bytes(upload, *, max_bytes: int = AUDIO_MAX_BYTES) -> bytes:
    data = upload.file.read(max_bytes + 1)
    if not data:
        raise AudioValidationError("audio_required")
    if len(data) > max_bytes:
        raise AudioValidationError("audio_too_large")
    return data


def _suffix_for_mime(mime_type: str) -> str:
    return {
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
        "audio/webm": ".webm",
    }.get(mime_type, ".bin")


def write_secure_temp_audio(data: bytes, mime_type: str) -> Path:
    suffix = _suffix_for_mime(mime_type)
    handle, name = tempfile.mkstemp(prefix="thati-aud-", suffix=suffix)
    path = Path(name)
    try:
        os.write(handle, data)
        os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        os.close(handle)
    return path


def needs_wav_conversion(mime_type: str) -> bool:
    return _canonical_mime(mime_type) not in _NATIVE_PROVIDER_TYPES


def provider_audio_mime(mime_type: str) -> str:
    """Gemini Interactions accepts audio/m4a, not audio/mp4."""
    mime = _canonical_mime(mime_type)
    if mime == "audio/mp4":
        return "audio/m4a"
    return mime


def prepare_provider_audio(path: Path, mime_type: str) -> tuple[Path, str]:
    if not needs_wav_conversion(mime_type):
        return path, provider_audio_mime(mime_type)
    return convert_to_16khz_mono_wav(path), "audio/wav"


def convert_to_16khz_mono_wav(source: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise AudioValidationError("conversion_unavailable")
    handle, name = tempfile.mkstemp(prefix="thati-aud-wav-", suffix=".wav")
    os.close(handle)
    dest = Path(name)
    try:
        completed = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(dest),
            ],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if completed.returncode != 0 or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise AudioValidationError("conversion_failed")
        os.chmod(dest, 0o600)
    except AudioValidationError:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise AudioValidationError("conversion_failed") from exc
    return dest
