from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from thati.clients import FraudClient, get_fraud_client
from thati.config import get_settings
from thati.db import match_entities, persist_analysis
from thati.errors import ProviderError, ProviderUnavailableError
from thati.rate_limit import analyze_limiter
from thati.schemas import AnalysisResponse, BlacklistMatch, TextAnalyzeRequest

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/text", response_model=AnalysisResponse)
def analyze_text(
    payload: TextAnalyzeRequest,
    request: Request,
    fraud_client: Annotated[FraudClient, Depends(get_fraud_client)],
) -> AnalysisResponse:
    settings = get_settings()
    if not analyze_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail={"error": "rate_limited"})

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail={"error": "text_required"})
    if len(payload.text) > settings.analyze_max_chars:
        raise HTTPException(status_code=422, detail={"error": "text_too_long"})

    try:
        assessment = fraud_client.analyze_text(text)
        analysis_id = persist_analysis(
            settings.sqlite_path,
            source_type="text",
            source_text=text,
            assessment=assessment,
        )
        hits = match_entities(settings.sqlite_path, assessment.entities)
    except ProviderUnavailableError:
        raise HTTPException(
            status_code=503, detail={"error": "provider_unavailable"}
        ) from None
    except ProviderError:
        raise HTTPException(status_code=502, detail={"error": "provider_error"}) from None
    except Exception:
        raise HTTPException(status_code=500, detail={"error": "internal_error"}) from None

    return AnalysisResponse(
        analysis_id=analysis_id,
        source_type="text",
        assessment=assessment,
        known_blacklist_matches=[BlacklistMatch.model_validate(hit) for hit in hits],
    )
