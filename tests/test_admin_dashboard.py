"""Human review dashboard: admin payload, safe rendering, and URL approval."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from thati.config import get_settings
from tests.test_analyze_text import OTP_PHISHING
from tests.test_review_workflow import ADMIN

FICTIONAL_URL = "https://kbz-secure-login.example/otp"
REPORT_NOTE = "OTP phishing — fictional bank URL and phone"


def _url_index(payload: dict) -> int:
    for index, entity in enumerate(payload["assessment"]["entities"]):
        if entity["type"] == "url":
            return index
    raise AssertionError("expected a url entity")


def test_admin_page_served(client: TestClient) -> None:
    response = client.get("/admin")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert 'id="admin-token"' in html
    assert 'src="/static/admin.js"' in html
    assert "innerHTML" not in html


def test_admin_js_never_uses_innerhtml() -> None:
    script = Path("web/admin.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "sessionStorage" in script
    assert "entity_indexes" in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script


def test_admin_json_hides_hashes_and_raw_identifiers(client: TestClient) -> None:
    analyze = client.post("/api/analyze/text", json={"text": OTP_PHISHING, "language": "my"})
    analysis_id = analyze.json()["analysis_id"]
    report_id = client.post(
        "/api/reports",
        json={"analysis_id": analysis_id, "note": REPORT_NOTE},
    ).json()["id"]

    listed = client.get("/api/admin/reports", headers=ADMIN)
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["reports"]
    report = next(item for item in payload["reports"] if item["id"] == report_id)
    dumped = json.dumps(report)
    assert "normalized_value_hash" not in dumped
    assert "exact_value" not in dumped
    assert FICTIONAL_URL not in dumped
    assert report["source_type"] == "text"
    assert report["source_excerpt"]
    assert report["risk_level"]
    assert report["evidence"]
    assert report["note"] == REPORT_NOTE
    types = {entity["entity_type"] for entity in report["entities"]}
    assert "url" in types
    assert "phone" in types
    for entity in report["entities"]:
        assert "index" in entity
        assert "masked_value" in entity
        assert "eligible" in entity
        assert entity["masked_value"] != FICTIONAL_URL


def test_approve_requires_selected_eligible_entity(client: TestClient) -> None:
    analyze = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    analysis_id = analyze.json()["analysis_id"]
    report_id = client.post("/api/reports", json={"analysis_id": analysis_id}).json()["id"]

    empty = client.post(
        f"/api/admin/reports/{report_id}/approve",
        headers=ADMIN,
        json={"entity_indexes": []},
    )
    assert empty.status_code == 422
    assert empty.json()["error"] == "invalid_request"

    connection = sqlite3.connect(get_settings().sqlite_path)
    try:
        analysis_row_id, result_json = connection.execute(
            "SELECT analysis_id, result_json FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        payload = json.loads(result_json)
        for entity in payload["entities"]:
            entity["exact_value"] = ""
        connection.execute(
            "UPDATE analyses SET result_json = ? WHERE id = ?",
            (json.dumps(payload), analysis_row_id),
        )
        connection.commit()
    finally:
        connection.close()

    no_eligible = client.post(
        f"/api/admin/reports/{report_id}/approve",
        headers=ADMIN,
        json={"entity_indexes": [0]},
    )
    assert no_eligible.status_code == 422
    assert no_eligible.json()["error"] == "no_eligible_entities"
    check = client.get(
        "/api/blacklist/check",
        params={"entity_type": "url", "value": FICTIONAL_URL},
    )
    assert check.json()["matched"] is False


def test_manual_flow_approve_fictional_url_then_public_check(client: TestClient) -> None:
    analyzed = client.post("/api/analyze/text", json={"text": OTP_PHISHING, "language": "my"})
    assert analyzed.status_code == 200
    analysis = analyzed.json()
    analysis_id = analysis["analysis_id"]
    url_index = _url_index(analysis)

    reported = client.post(
        "/api/reports",
        json={"analysis_id": analysis_id, "note": REPORT_NOTE},
    )
    assert reported.status_code == 200
    report_id = reported.json()["id"]

    queue = client.get("/api/admin/reports", params={"status": "pending"}, headers=ADMIN)
    assert queue.status_code == 200
    pending = queue.json()["reports"]
    assert pending[0]["id"] == report_id
    assert pending[0]["source_type"] == "text"
    assert pending[0]["risk_level"]
    assert pending[0]["source_excerpt"]
    assert pending[0]["evidence"]
    assert pending[0]["note"] == REPORT_NOTE

    approved = client.post(
        f"/api/admin/reports/{report_id}/approve",
        headers=ADMIN,
        json={"entity_indexes": [url_index]},
    )
    assert approved.status_code == 200
    assert approved.json() == {"status": "approved"}
    assert "normalized" not in str(approved.json()).lower()

    hit = client.get(
        "/api/blacklist/check",
        params={"entity_type": "url", "value": FICTIONAL_URL},
    )
    assert hit.status_code == 200
    body = hit.json()
    assert body["matched"] is True
    assert body["entity_type"] == "url"
    assert "*" in body["masked_display_value"]
    assert "normalized_value_hash" not in body
    assert body["masked_display_value"] != FICTIONAL_URL
    assert FICTIONAL_URL not in hit.text

    miss_phone = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": "09-123456789"},
    )
    assert miss_phone.json()["matched"] is False
