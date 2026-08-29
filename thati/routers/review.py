from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from thati.auth import require_admin
from thati.config import get_settings
from thati.db import (
    approve_report,
    create_pending_report,
    get_analysis,
    list_reports,
    lookup_blacklist,
    reject_report,
)
from thati.schemas import EntityType, RiskLevel

reports_router = APIRouter(prefix="/api/reports", tags=["reports"])
blacklist_router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class CreateReportRequest(BaseModel):
    analysis_id: UUID
    note: str = ""


class CreateReportResponse(BaseModel):
    id: str
    status: str = "pending"


class ApproveReportRequest(BaseModel):
    entity_indexes: list[int] = Field(..., min_length=1)
    reason: str = "human_reviewed"
    risk_level: RiskLevel = "high"


@reports_router.post("", response_model=CreateReportResponse)
def submit_report(payload: CreateReportRequest) -> CreateReportResponse:
    settings = get_settings()
    analysis_id = str(payload.analysis_id)
    if get_analysis(settings.sqlite_path, analysis_id) is None:
        raise HTTPException(status_code=404, detail={"error": "analysis_not_found"})
    report_id = create_pending_report(
        settings.sqlite_path,
        analysis_id=analysis_id,
        note=payload.note,
    )
    return CreateReportResponse(id=report_id, status="pending")


@blacklist_router.get("/check")
def check_blacklist(entity_type: EntityType, value: str) -> dict[str, object]:
    if not value.strip():
        raise HTTPException(status_code=422, detail={"error": "value_required"})
    hit = lookup_blacklist(
        get_settings().sqlite_path,
        entity_type=entity_type,
        value=value,
    )
    if hit is None:
        return {"matched": False, "entity_type": entity_type}
    return hit


@admin_router.get("/reports")
def admin_list_reports(status: str | None = "pending") -> dict[str, object]:
    rows = list_reports(get_settings().sqlite_path, status=status)
    return {"reports": rows}


@admin_router.post("/reports/{report_id}/approve")
def admin_approve_report(
    report_id: str,
    payload: ApproveReportRequest,
) -> dict[str, object]:
    try:
        approve_report(
            get_settings().sqlite_path,
            report_id,
            entity_indexes=payload.entity_indexes,
            reason=payload.reason,
            risk_level=payload.risk_level,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "report_not_found"}) from None
    except ValueError as exc:
        code = str(exc)
        status = 409 if code == "report_not_pending" else 422
        raise HTTPException(status_code=status, detail={"error": code}) from None
    return {"status": "approved"}


@admin_router.post("/reports/{report_id}/reject")
def admin_reject_report(report_id: str) -> dict[str, object]:
    try:
        reject_report(get_settings().sqlite_path, report_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "report_not_found"}) from None
    except ValueError:
        raise HTTPException(status_code=409, detail={"error": "report_not_pending"}) from None
    return {"status": "rejected"}
