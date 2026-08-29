"""SQLite persistence. All queries are parameterized. Blacklist writes are human-only."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from thati.identifiers import excerpt_source, hash_identifier, hash_source, mask_identifier
from thati.schemas import (
    EntityType,
    ExtractedEntity,
    FraudAssessment,
    RiskLevel,
    SourceType,
)

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        source_excerpt TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        analysis_id TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        FOREIGN KEY (analysis_id) REFERENCES analyses(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS blacklist_entries (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        normalized_value_hash TEXT NOT NULL,
        masked_display_value TEXT NOT NULL,
        reason TEXT NOT NULL,
        reports_count INTEGER NOT NULL DEFAULT 1,
        risk_level TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        UNIQUE (entity_type, normalized_value_hash)
    )
    """,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode=WAL;")
    return connection


def ensure_database(path: Path) -> None:
    connection = connect(path)
    try:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def database_is_ready(path: Path) -> bool:
    try:
        ensure_database(path)
    except OSError:
        return False
    return True


def persist_analysis(
    path: Path,
    *,
    source_type: SourceType,
    source_text: str,
    assessment: FraudAssessment,
) -> str:
    analysis_id = str(uuid4())
    excerpt = excerpt_source(source_text)
    payload = assessment.model_dump()
    payload["extracted_text"] = excerpt
    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO analyses (
                id, source_type, source_hash, source_excerpt, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                source_type,
                hash_source(source_text),
                excerpt,
                json.dumps(payload, ensure_ascii=False),
                _now(),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return analysis_id


def get_analysis(path: Path, analysis_id: str) -> sqlite3.Row | None:
    connection = connect(path)
    try:
        return connection.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    finally:
        connection.close()


def create_pending_report(path: Path, *, analysis_id: str, note: str) -> str:
    if get_analysis(path, analysis_id) is None:
        raise KeyError("analysis_not_found")
    report_id = str(uuid4())
    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO reports (id, analysis_id, note, status, created_at, reviewed_at)
            VALUES (?, ?, ?, 'pending', ?, NULL)
            """,
            (report_id, analysis_id, note, _now()),
        )
        connection.commit()
    finally:
        connection.close()
    return report_id


def list_reports(path: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    connection = connect(path)
    try:
        if status:
            rows = connection.execute(
                """
                SELECT reports.*, analyses.source_excerpt, analyses.result_json
                FROM reports
                JOIN analyses ON analyses.id = reports.analysis_id
                WHERE reports.status = ?
                ORDER BY reports.created_at ASC
                """,
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT reports.*, analyses.source_excerpt, analyses.result_json
                FROM reports
                JOIN analyses ON analyses.id = reports.analysis_id
                ORDER BY reports.created_at ASC
                """
            ).fetchall()
        return [_report_payload(row) for row in rows]
    finally:
        connection.close()


def _masked_entities(result_json: str) -> list[dict[str, Any]]:
    payload = json.loads(result_json)
    entities = []
    for index, item in enumerate(payload.get("entities", [])):
        entity_type = item["type"]
        exact = item["exact_value"]
        entities.append(
            {
                "index": index,
                "entity_type": entity_type,
                "masked_value": mask_identifier(entity_type, exact),
            }
        )
    return entities


def _report_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "analysis_id": row["analysis_id"],
        "note": row["note"],
        "status": row["status"],
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
        "source_excerpt": row["source_excerpt"],
        "entities": _masked_entities(row["result_json"]),
    }


def get_report(path: Path, report_id: str) -> sqlite3.Row | None:
    connection = connect(path)
    try:
        return connection.execute(
            """
            SELECT reports.*, analyses.result_json, analyses.source_excerpt
            FROM reports
            JOIN analyses ON analyses.id = reports.analysis_id
            WHERE reports.id = ?
            """,
            (report_id,),
        ).fetchone()
    finally:
        connection.close()


def reject_report(path: Path, report_id: str) -> None:
    row = get_report(path, report_id)
    if row is None:
        raise KeyError("report_not_found")
    if row["status"] != "pending":
        raise ValueError("report_not_pending")
    connection = connect(path)
    try:
        connection.execute(
            """
            UPDATE reports
            SET status = 'rejected', reviewed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (_now(), report_id),
        )
        connection.commit()
    finally:
        connection.close()


def approve_report(
    path: Path,
    report_id: str,
    *,
    entity_indexes: Iterable[int],
    reason: str,
    risk_level: RiskLevel,
) -> list[str]:
    """Human-only blacklist write. Selected entity indexes are hashed, never stored raw."""
    indexes = list(dict.fromkeys(entity_indexes))
    if not indexes:
        raise ValueError("entity_indexes_required")
    row = get_report(path, report_id)
    if row is None:
        raise KeyError("report_not_found")
    if row["status"] != "pending":
        raise ValueError("report_not_pending")
    assessment = json.loads(row["result_json"])
    entities = assessment.get("entities", [])
    selected: list[dict[str, Any]] = []
    for index in indexes:
        if index < 0 or index >= len(entities):
            raise ValueError("invalid_entity_index")
        selected.append(entities[index])

    now = _now()
    entry_ids: list[str] = []
    connection = connect(path)
    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            UPDATE reports
            SET status = 'approved', reviewed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, report_id),
        )
        for item in selected:
            entity_type: EntityType = item["type"]
            exact_value = item["exact_value"]
            value_hash = hash_identifier(entity_type, exact_value)
            masked = mask_identifier(entity_type, exact_value)
            existing = connection.execute(
                """
                SELECT id, reports_count FROM blacklist_entries
                WHERE entity_type = ? AND normalized_value_hash = ?
                """,
                (entity_type, value_hash),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE blacklist_entries
                    SET reports_count = ?, last_seen_at = ?, reason = ?,
                        risk_level = ?, masked_display_value = ?
                    WHERE id = ?
                    """,
                    (
                        existing["reports_count"] + 1,
                        now,
                        reason,
                        risk_level,
                        masked,
                        existing["id"],
                    ),
                )
                entry_ids.append(existing["id"])
            else:
                entry_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO blacklist_entries (
                        id, entity_type, normalized_value_hash, masked_display_value,
                        reason, reports_count, risk_level, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        entity_type,
                        value_hash,
                        masked,
                        reason,
                        risk_level,
                        now,
                        now,
                    ),
                )
                entry_ids.append(entry_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return entry_ids


def lookup_blacklist(
    path: Path, *, entity_type: EntityType, value: str
) -> dict[str, Any] | None:
    value_hash = hash_identifier(entity_type, value)
    connection = connect(path)
    try:
        row = connection.execute(
            """
            SELECT entity_type, masked_display_value, reports_count, risk_level
            FROM blacklist_entries
            WHERE entity_type = ? AND normalized_value_hash = ?
            """,
            (entity_type, value_hash),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return {
        "matched": True,
        "entity_type": row["entity_type"],
        "masked_display_value": row["masked_display_value"],
        "reports_count": row["reports_count"],
        "risk_level": row["risk_level"],
    }


def match_entities(path: Path, entities: list[ExtractedEntity]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        key = (entity.type, hash_identifier(entity.type, entity.exact_value))
        if key in seen:
            continue
        seen.add(key)
        hit = lookup_blacklist(path, entity_type=entity.type, value=entity.exact_value)
        if hit:
            matches.append(hit)
    return matches
