from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from thati.extract import normalize_digits
from thati.mock_client import MockFraudClient

OTP_PHISHING = (
    "မင်္ဂလာပါ KBZ ဘဏ်မှ ဖြစ်ပါတယ်။ အကောင့်ပိတ်ပါမည်။ "
    "09-123456789 သို့ ငွေလွှဲပြီး OTP ပို့ပေးပါ။ "
    "https://kbz-secure-login.example/otp"
)
BENIGN = "မနက်ဖြန် ညနေ ၅ နာရီမှာ ထမင်းစားကြမယ်။ ကောင်းသောနေ့ဖြစ်ပါစေ။"
MYANMAR_PHONE = "မိတ်ဆွေကို ၀၉၁၂၃၄၅၆၇၈၉ မှာ ဖုန်းဆက်ပေးပါ။"
URL_ONLY = "အသေးစိတ် https://docs.example.org/help မှာ ဖတ်နိုင်ပါတယ်။"


def _assert_no_leak(response) -> None:
    body = response.text
    assert "Traceback" not in body
    assert "GEMINI_API_KEY" not in body
    assert "AQ." not in body


def test_mock_client_module_has_no_external_sdk() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in ("thati/mock_client.py", "thati/extract.py"):
        source = (root / relative).read_text(encoding="utf-8")
        assert "google" not in source
        assert "genai" not in source
        assert "openai" not in source


def test_critical_otp_phishing_message(client: TestClient) -> None:
    response = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    _assert_no_leak(response)
    assert response.status_code == 200
    payload = response.json()
    UUID(payload["analysis_id"])
    assessment = payload["assessment"]
    assert assessment["risk_level"] == "critical"
    assert assessment["likely_fraud"] is True
    quotes = [item["quote"] for item in assessment["evidence"]]
    assert any("OTP" in quote for quote in quotes)
    assert any("အကောင့်ပိတ်" in quote for quote in quotes)
    assert any(item["type"] == "url" for item in assessment["entities"])
    assert any(item["type"] == "phone" for item in assessment["entities"])
    assert assessment["myanmar_safe_actions"]
    assert assessment["uncertainty"]


def test_benign_message_is_not_high_or_critical(client: TestClient) -> None:
    response = client.post("/api/analyze/text", json={"text": BENIGN})
    _assert_no_leak(response)
    assert response.status_code == 200
    assessment = response.json()["assessment"]
    assert assessment["risk_level"] == "low"
    assert assessment["likely_fraud"] is False
    assert assessment["risk_score"] < 25


def test_myanmar_digits_kept_in_displayed_evidence(client: TestClient) -> None:
    response = client.post("/api/analyze/text", json={"text": MYANMAR_PHONE})
    _assert_no_leak(response)
    assert response.status_code == 200
    assessment = response.json()["assessment"]
    phones = [item for item in assessment["entities"] if item["type"] == "phone"]
    assert phones
    exact = phones[0]["exact_value"]
    assert "၀၉" in exact
    assert "09" not in exact
    assert normalize_digits(exact).startswith("09")
    assert exact in assessment["extracted_text"]
    assert assessment["risk_level"] in {"low", "medium"}


def test_url_extraction(client: TestClient) -> None:
    response = client.post("/api/analyze/text", json={"text": URL_ONLY})
    _assert_no_leak(response)
    assert response.status_code == 200
    assessment = response.json()["assessment"]
    urls = [item["exact_value"] for item in assessment["entities"] if item["type"] == "url"]
    assert urls == ["https://docs.example.org/help"]
    assert "https://docs.example.org/help" in [item["quote"] for item in assessment["evidence"]]
    assert assessment["risk_level"] != "critical"


def test_empty_input_is_rejected(client: TestClient) -> None:
    for text in ("", "   ", "\n"):
        response = client.post("/api/analyze/text", json={"text": text})
        _assert_no_leak(response)
        assert response.status_code == 422
        assert response.json() == {"error": "text_required"}


def test_oversized_input_is_rejected(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("ANALYZE_MAX_CHARS", "20")
    from thati.config import reset_settings

    reset_settings()
    response = client.post("/api/analyze/text", json={"text": "က" * 21})
    _assert_no_leak(response)
    assert response.status_code == 422
    assert response.json() == {"error": "text_too_long"}


def test_rate_limiting_per_ip(client: TestClient) -> None:
    from thati.rate_limit import analyze_limiter

    analyze_limiter.configure(max_requests=2, window_seconds=60)
    analyze_limiter.reset()
    body = {"text": BENIGN}
    assert client.post("/api/analyze/text", json=body).status_code == 200
    assert client.post("/api/analyze/text", json=body).status_code == 200
    limited = client.post("/api/analyze/text", json=body)
    _assert_no_leak(limited)
    assert limited.status_code == 429
    assert limited.json() == {"error": "rate_limited"}


def test_mock_client_is_deterministic() -> None:
    client = MockFraudClient()
    first = client.analyze_text(OTP_PHISHING)
    second = client.analyze_text(OTP_PHISHING)
    assert first.risk_score == second.risk_score
    assert [item.quote for item in first.evidence] == [item.quote for item in second.evidence]
