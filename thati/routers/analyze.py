from fastapi import APIRouter, HTTPException, Request

from thati.clients import get_fraud_client
from thati.config import get_settings
from thati.rate_limit import analyze_limiter
from thati.schemas import AnalysisResponse, TextAnalyzeRequest

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/text", response_model=AnalysisResponse)
def analyze_text(payload: TextAnalyzeRequest, request: Request) -> AnalysisResponse:
    settings = get_settings()
    if not analyze_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail={"error": "rate_limited"})

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail={"error": "text_required"})
    if len(payload.text) > settings.analyze_max_chars:
        raise HTTPException(status_code=422, detail={"error": "text_too_long"})

    try:
        client = get_fraud_client()
        assessment = client.analyze_text(text)
    except RuntimeError:
        raise HTTPException(status_code=501, detail={"error": "live_mode_unavailable"}) from None
    except Exception:
        raise HTTPException(status_code=500, detail={"error": "internal_error"}) from None

    return AnalysisResponse(
        source_type="text",
        assessment=assessment,
        known_blacklist_matches=[],
    )
