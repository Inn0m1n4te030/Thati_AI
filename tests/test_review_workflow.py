import sqlite3

from fastapi.testclient import TestClient

from thati.config import get_settings
from thati.identifiers import SOURCE_EXCERPT_LIMIT, hash_identifier, normalize_identifier
from tests.test_analyze_text import OTP_PHISHING

ADMIN = {"X-Admin-Token": "test-admin-token"}
PHONE = "09-123456789"


def _phone_index(payload: dict) -> int:
    for index, entity in enumerate(payload["assessment"]["entities"]):
        if entity["type"] == "phone":
            return index
    raise AssertionError("expected a phone entity")


def _blacklist_rows() -> list[sqlite3.Row]:
    connection = sqlite3.connect(get_settings().sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        return list(connection.execute("SELECT * FROM blacklist_entries"))
    finally:
        connection.close()


def test_report_matches_only_after_human_approval(client: TestClient) -> None:
    analyzed = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert analyzed.status_code == 200
    body = analyzed.json()
    analysis_id = body["analysis_id"]
    assert body["known_blacklist_matches"] == []
    phone_index = _phone_index(body)

    before = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": PHONE},
    )
    assert before.status_code == 200
    assert before.json()["matched"] is False
    assert PHONE not in before.text

    reported = client.post(
        "/api/reports",
        json={"analysis_id": analysis_id, "note": "OTP phishing pattern"},
    )
    assert reported.status_code == 200
    assert reported.json()["status"] == "pending"
    report_id = reported.json()["id"]
    assert _blacklist_rows() == []

    still_pending = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": PHONE},
    )
    assert still_pending.json()["matched"] is False

    denied = client.post(
        f"/api/admin/reports/{report_id}/approve",
        json={"entity_indexes": [phone_index]},
    )
    assert denied.status_code == 401

    approved = client.post(
        f"/api/admin/reports/{report_id}/approve",
        json={
            "entity_indexes": [phone_index],
            "reason": "human reviewed",
            "risk_level": "critical",
        },
        headers=ADMIN,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    after = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": PHONE},
    )
    assert after.status_code == 200
    assert after.json()["matched"] is True
    assert after.json()["masked_display_value"]
    assert PHONE not in after.text
    assert "09123456789" not in after.text

    myanmar = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": "၀၉၁၂၃၄၅၆၇၈၉"},
    )
    assert myanmar.json()["matched"] is True

    rows = _blacklist_rows()
    assert len(rows) == 1
    stored = " ".join(str(value) for value in rows[0])
    assert PHONE not in stored
    assert "09123456789" not in stored
    assert rows[0]["normalized_value_hash"] == hash_identifier("phone", PHONE)
    assert normalize_identifier("phone", "၀၉၁၂၃၄၅၆၇၈၉") == normalize_identifier(
        "phone", PHONE
    )

    second = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert second.status_code == 200
    matches = second.json()["known_blacklist_matches"]
    assert any(item["entity_type"] == "phone" and item["matched"] is True for item in matches)
    assert all(PHONE not in item.get("masked_display_value", "") for item in matches)


def test_reject_writes_no_blacklist_entry(client: TestClient) -> None:
    analyzed = client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    analysis_id = analyzed.json()["analysis_id"]
    report_id = client.post(
        "/api/reports",
        json={"analysis_id": analysis_id, "note": "false alarm"},
    ).json()["id"]
    rejected = client.post(
        f"/api/admin/reports/{report_id}/reject",
        headers=ADMIN,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert _blacklist_rows() == []
    check = client.get(
        "/api/blacklist/check",
        params={"entity_type": "phone", "value": PHONE},
    )
    assert check.json()["matched"] is False


def test_analyze_does_not_auto_blacklist(client: TestClient) -> None:
    client.post("/api/analyze/text", json={"text": OTP_PHISHING})
    assert _blacklist_rows() == []


def test_admin_list_requires_token(client: TestClient) -> None:
    response = client.get("/api/admin/reports")
    assert response.status_code == 401
    listed = client.get("/api/admin/reports", headers=ADMIN)
    assert listed.status_code == 200
    assert "reports" in listed.json()


def test_source_excerpt_is_limited(client: TestClient) -> None:
    import json

    text = "OTP ပို့ပေးပါ " + ("က" * 1500)
    analyzed = client.post("/api/analyze/text", json={"text": text})
    analysis_id = analyzed.json()["analysis_id"]
    connection = sqlite3.connect(get_settings().sqlite_path)
    try:
        excerpt, stored_json = connection.execute(
            "SELECT source_excerpt, result_json FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    finally:
        connection.close()
    stored = json.loads(stored_json)
    assert len(excerpt) == SOURCE_EXCERPT_LIMIT
    assert stored["extracted_text"] == excerpt
