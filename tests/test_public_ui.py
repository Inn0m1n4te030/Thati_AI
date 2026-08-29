from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_analyze_text import OTP_PHISHING


def test_public_page_has_spec_landmarks(client: TestClient) -> None:
    html = client.get("/").text
    assert "Thati AI" in html
    assert 'id="mode-badge"' in html
    assert "သံသယရှိသော စာကို ကူးထည့်ပါ" in html
    assert 'id="analyze"' in html
    assert 'id="disclaimer"' in html
    assert 'href="/admin"' in html
    assert 'id="blacklist-form"' in html
    assert 'id="report-form"' in html
    assert "innerHTML" not in html
    assert "googleapis" not in html
    assert "cdn." not in html.lower()
    assert "GEMINI_API_KEY" not in html


def test_public_js_never_leaks_key_or_uses_innerhtml() -> None:
    script = Path("web/app.js").read_text(encoding="utf-8")
    css = Path("web/styles.css").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "GEMINI" not in script
    assert "AQ." not in script
    assert "fonts.googleapis" not in css
    assert "prefers-reduced-motion" in css
    assert "/health" in script
    assert "/api/reports" in script
    assert "/api/blacklist/check" in script
    assert "canShowScore" in script


def test_public_text_analyze_report_and_blacklist(client: TestClient) -> None:
    analyzed = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert analyzed.status_code == 200
    analysis_id = analyzed.json()["analysis_id"]
    reported = client.post(
        "/api/reports",
        json={"analysis_id": analysis_id, "note": "public ui"},
    )
    assert reported.status_code == 200
    assert reported.json()["status"] == "pending"
    check = client.get(
        "/api/blacklist/check",
        params={"entity_type": "url", "value": "https://kbz-secure-login.example/otp"},
    )
    assert check.status_code == 200
    assert check.json()["matched"] is False
