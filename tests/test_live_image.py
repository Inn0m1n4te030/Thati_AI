from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from thati.clients import set_fraud_client
from thati.config import reset_settings
from thati.live_client import (
    GeminiFraudClient,
    image_generate_contents,
    live_image_generate_config,
)
from thati.prompts import IMAGE_SYSTEM_PROMPT, IMAGE_USER_PROMPT
from thati.schemas import FraudAssessment
from tests.test_analyze_image import PNG_BYTES
from tests.test_schemas import SOURCE, _valid_assessment

FAKE_FILE_URI = "https://generativelanguage.googleapis.com/v1beta/files/thati-shot"
FAKE_FILE_NAME = "files/thati-shot"


def _fake_response(text: str = SOURCE) -> SimpleNamespace:
    return SimpleNamespace(
        parsed=FraudAssessment.model_validate(_valid_assessment(extracted_text=text))
    )


def test_image_request_schema_uses_files_api_uri() -> None:
    contents = image_generate_contents(FAKE_FILE_URI, "image/png")
    assert contents[0] == {
        "file_data": {
            "file_uri": FAKE_FILE_URI,
            "mime_type": "image/png",
        }
    }
    assert contents[1] == IMAGE_USER_PROMPT
    config = live_image_generate_config()
    assert config["response_schema"] is FraudAssessment
    assert config["response_mime_type"] == "application/json"
    assert config["system_instruction"] == IMAGE_SYSTEM_PROMPT
    assert "Do not guess unreadable" in IMAGE_SYSTEM_PROMPT
    assert "visible" in IMAGE_SYSTEM_PROMPT.lower()


def test_live_image_uploads_uri_schema_and_deletes_provider_file() -> None:
    captured: dict[str, object] = {}
    deleted: list[str] = []
    uploaded_paths: list[str] = []

    def fake_upload(*, file: str, config: dict[str, str] | None = None) -> SimpleNamespace:
        uploaded_paths.append(file)
        assert Path(file).exists()
        assert config == {"mime_type": "image/png"}
        return SimpleNamespace(name=FAKE_FILE_NAME, uri=FAKE_FILE_URI, mime_type="image/png")

    def fake_delete(*, name: str, config: object = None) -> None:
        deleted.append(name)

    def fake_generate(*, model: str, contents: object, config: dict[str, object]) -> SimpleNamespace:
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return _fake_response(SOURCE)

    client = GeminiFraudClient(
        model="gemini-3.7-flash",
        generate_content=fake_generate,
        files_upload=fake_upload,
        files_delete=fake_delete,
    )
    path = Path("shot.png")
    path.write_bytes(PNG_BYTES)
    try:
        assessment = client.analyze_image(path, "image/png")
    finally:
        path.unlink(missing_ok=True)

    assert assessment.extracted_text == SOURCE
    assert captured["config"]["response_schema"] is FraudAssessment
    assert captured["config"]["system_instruction"] == IMAGE_SYSTEM_PROMPT
    assert captured["contents"] == image_generate_contents(FAKE_FILE_URI, "image/png")
    assert deleted == [FAKE_FILE_NAME]


def test_live_image_http_cleanup_on_success_and_failure(
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

    def fake_generate(**_kwargs: object) -> SimpleNamespace:
        return _fake_response(SOURCE)

    set_fraud_client(
        GeminiFraudClient(
            model="gemini-3.7-flash",
            generate_content=fake_generate,
            files_upload=fake_upload,
            files_delete=fake_delete,
        )
    )
    ok = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert ok.status_code == 200
    assert ok.json()["source_type"] == "screenshot"
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
            generate_content=boom,
            files_upload=fake_upload,
            files_delete=fake_delete,
        )
    )
    failed = client.post(
        "/api/analyze/image",
        files={"file": ("shot.png", PNG_BYTES, "image/png")},
    )
    assert failed.status_code == 502
    assert failed.json() == {"error": "provider_error"}
    assert deleted == [FAKE_FILE_NAME]
    assert local_paths
    assert all(not Path(path).exists() for path in local_paths)
    assert "Traceback" not in failed.text
    assert "secret-should-not-leak" not in failed.text


def test_provider_file_deleted_if_generate_raises() -> None:
    deleted: list[str] = []

    def fake_upload(*, file: str, config: dict[str, str] | None = None) -> SimpleNamespace:
        return SimpleNamespace(name=FAKE_FILE_NAME, uri=FAKE_FILE_URI)

    def fake_delete(*, name: str, config: object = None) -> None:
        deleted.append(name)

    def boom(**_kwargs: object) -> SimpleNamespace:
        raise RuntimeError("mid-request")

    live = GeminiFraudClient(
        model="gemini-3.7-flash",
        generate_content=boom,
        files_upload=fake_upload,
        files_delete=fake_delete,
    )
    path = Path("shot.png")
    path.write_bytes(PNG_BYTES)
    try:
        try:
            live.analyze_image(path, "image/png")
        except Exception:
            pass
    finally:
        path.unlink(missing_ok=True)
    assert deleted == [FAKE_FILE_NAME]
