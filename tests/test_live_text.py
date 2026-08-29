from types import SimpleNamespace

from fastapi.testclient import TestClient

from thati.clients import set_fraud_client
from thati.config import reset_settings
from thati.live_client import GeminiFraudClient, live_generate_config, wrap_untrusted_message
from thati.prompts import EVIDENCE_FIRST_SYSTEM_PROMPT
from thati.schemas import FraudAssessment
from tests.test_analyze_text import OTP_PHISHING
from tests.test_schemas import SOURCE, _valid_assessment


def _fake_response(text: str = SOURCE) -> SimpleNamespace:
    return SimpleNamespace(parsed=FraudAssessment.model_validate(_valid_assessment(extracted_text=text)))


def test_live_config_uses_pydantic_schema_and_evidence_prompt() -> None:
    config = live_generate_config()
    assert config["response_schema"] is FraudAssessment
    assert config["response_mime_type"] == "application/json"
    assert config["system_instruction"] == EVIDENCE_FIRST_SYSTEM_PROMPT
    assert "UNTRUSTED" in EVIDENCE_FIRST_SYSTEM_PROMPT or "untrusted" in EVIDENCE_FIRST_SYSTEM_PROMPT
    assert "Myanmar" in EVIDENCE_FIRST_SYSTEM_PROMPT
    assert "probability" in EVIDENCE_FIRST_SYSTEM_PROMPT.lower()


def test_provider_receives_schema_prompt_and_wrapped_message() -> None:
    captured: dict[str, object] = {}

    def fake_generate_content(*, model: str, contents: str, config: dict[str, object]) -> SimpleNamespace:
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return _fake_response(SOURCE)

    client = GeminiFraudClient(model="gemini-3.7-flash", generate_content=fake_generate_content)
    assessment = client.analyze_text(SOURCE)

    assert captured["model"] == "gemini-3.7-flash"
    config = captured["config"]
    assert isinstance(config, dict)
    assert config["response_schema"] is FraudAssessment
    assert config["system_instruction"] == EVIDENCE_FIRST_SYSTEM_PROMPT
    assert config["response_mime_type"] == "application/json"
    assert captured["contents"] == wrap_untrusted_message(SOURCE)
    assert SOURCE in str(captured["contents"])
    assert SOURCE not in EVIDENCE_FIRST_SYSTEM_PROMPT
    assert assessment.extracted_text == SOURCE
    assert any("OTP" in item.quote for item in assessment.evidence)


def test_injected_live_client_makes_no_network_calls(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-should-not-leak")
    reset_settings()
    calls: list[dict[str, object]] = []

    def fake_generate_content(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return _fake_response(SOURCE)

    set_fraud_client(
        GeminiFraudClient(model="gemini-3.7-flash", generate_content=fake_generate_content)
    )
    response = client.post("/api/analyze/text", json={"text": SOURCE})
    assert response.status_code == 200
    assert "secret-should-not-leak" not in response.text
    assert "Traceback" not in response.text
    assert calls
    assert calls[0]["config"]["response_schema"] is FraudAssessment
    assert calls[0]["config"]["system_instruction"] == EVIDENCE_FIRST_SYSTEM_PROMPT
    assert SOURCE in str(calls[0]["contents"])


def test_live_without_api_key_returns_generic_error(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    reset_settings()
    set_fraud_client(None)
    response = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert response.status_code == 503
    assert response.json() == {"error": "provider_unavailable"}
    assert "Traceback" not in response.text
    assert "GEMINI_API_KEY" not in response.text


def test_provider_failure_is_generic(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-should-not-leak")
    reset_settings()

    def boom(**_kwargs: object) -> SimpleNamespace:
        raise TimeoutError("generativelanguage.googleapis.com timed out key=secret-should-not-leak")

    set_fraud_client(GeminiFraudClient(model="gemini-3.7-flash", generate_content=boom))
    response = client.post("/api/analyze/text", json={"text": SOURCE})
    assert response.status_code == 502
    assert response.json() == {"error": "provider_error"}
    assert "Traceback" not in response.text
    assert "secret-should-not-leak" not in response.text
    assert "timed out" not in response.text


def test_sanitize_drops_invented_quotes() -> None:
    from thati.live_client import sanitize_assessment
    from thati.schemas import EvidenceItem

    valid = FraudAssessment.model_validate(_valid_assessment())
    dirty = valid.model_copy(update={
        "evidence": [
            *valid.evidence,
            EvidenceItem.model_construct(
                quote="this quote is not in the source",
                myanmar_explanation="မူရင်းတွင် မရှိပါ။",
                severity="high",
            ),
        ]
    })
    clean = sanitize_assessment(dirty, SOURCE)
    assert all(item.quote in SOURCE for item in clean.evidence)
    assert all(item.quote != "this quote is not in the source" for item in clean.evidence)
