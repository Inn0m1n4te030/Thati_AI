"""Screenshot analysis is optional and must not change the text workflow."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from thati.image import IMAGE_MAX_BYTES
from thati.mock_client import SYNTHETIC_SCREENSHOT_TEXT
from tests.test_analyze_text import OTP_PHISHING

# 1x1 PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def test_public_page_enables_screenshot_tab(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'id="tab-image"' in html
    assert 'id="dropzone"' in html
    assert 'src="/static/app.js"' in html
    assert "innerHTML" not in html


def test_app_js_upload_states_without_innerhtml() -> None:
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "IMAGE_MAX_BYTES = 10 * 1024 * 1024" in script
    assert "dragover" in script
    assert "drop" in script
    assert "/api/analyze/image" in script
    assert "renderResult" in script
    assert "FormData" in script
    assert "remove-image" in script


def test_mock_png_returns_deterministic_screenshot_result(client: TestClient) -> None:
    first = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    second = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["source_type"] == "screenshot"
    assert body["assessment"]["extracted_text"] == SYNTHETIC_SCREENSHOT_TEXT
    assert body["assessment"] == second.json()["assessment"]
    assert any(item["type"] == "url" for item in body["assessment"]["entities"])


def test_mock_jpeg_is_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/analyze/image",
        files={"file": ("shot.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["source_type"] == "screenshot"


def test_rejects_non_png_jpeg(client: TestClient) -> None:
    gif = client.post(
        "/api/analyze/image",
        files={"file": ("shot.gif", b"GIF89a" + b"\x00" * 16, "image/gif")},
    )
    assert gif.status_code == 422
    assert gif.json() == {"error": "unsupported_image_type"}


def test_rejects_type_mismatch(client: TestClient) -> None:
    response = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", JPEG_BYTES, "image/png")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "unsupported_image_type"}


def test_rejects_image_over_10mb(client: TestClient) -> None:
    payload = JPEG_BYTES[:3] + b"\x00" * (IMAGE_MAX_BYTES)
    response = client.post(
        "/api/analyze/image",
        files={"file": ("huge.jpg", payload, "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "image_too_large"}


def test_image_temp_file_is_removed(client: TestClient, monkeypatch) -> None:
    created: list[Path] = []
    real_write = __import__("thati.image", fromlist=["write_secure_temp_image"]).write_secure_temp_image

    def tracking_write(data: bytes, mime_type: str) -> Path:
        path = real_write(data, mime_type)
        created.append(path)
        return path

    monkeypatch.setattr("thati.routers.analyze.write_secure_temp_image", tracking_write)
    response = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 200
    assert created
    assert all(not path.exists() for path in created)


def test_text_workflow_unchanged_after_screenshot(client: TestClient) -> None:
    image = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert image.status_code == 200
    text = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert text.status_code == 200
    payload = text.json()
    assert payload["source_type"] == "text"
    assert payload["assessment"]["risk_level"] == "critical"
    assert any(item["type"] == "phone" for item in payload["assessment"]["entities"])
