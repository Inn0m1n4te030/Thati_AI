"""PNG/JPEG upload checks and a private temporary file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

IMAGE_MAX_BYTES = 10 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


class ImageValidationError(ValueError):
    """User-facing image rejection; ``str(exc)`` is a stable error code."""


def detect_image_mime(header: bytes, declared_type: str | None) -> str:
    if header.startswith(PNG_MAGIC):
        sniffed = "image/png"
    elif header.startswith(JPEG_MAGIC):
        sniffed = "image/jpeg"
    else:
        raise ImageValidationError("unsupported_image_type")

    declared = (declared_type or "").split(";", 1)[0].strip().lower()
    if declared in {"", "application/octet-stream"}:
        return sniffed
    if declared in {"image/jpg", "image/jpeg"}:
        declared = "image/jpeg"
    if declared not in {"image/png", "image/jpeg"}:
        raise ImageValidationError("unsupported_image_type")
    if declared != sniffed:
        raise ImageValidationError("unsupported_image_type")
    return sniffed


def read_upload_bytes(upload, *, max_bytes: int = IMAGE_MAX_BYTES) -> bytes:
    data = upload.file.read(max_bytes + 1)
    if not data:
        raise ImageValidationError("image_required")
    if len(data) > max_bytes:
        raise ImageValidationError("image_too_large")
    return data


def write_secure_temp_image(data: bytes, mime_type: str) -> Path:
    suffix = ".png" if mime_type == "image/png" else ".jpg"
    handle, name = tempfile.mkstemp(prefix="thati-img-", suffix=suffix)
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
