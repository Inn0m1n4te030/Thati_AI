from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from thati.config import get_settings
from thati.db import database_is_ready, ensure_database
from thati.errors import ProviderError, ProviderUnavailableError
from thati.rate_limit import analyze_limiter
from thati.routers.analyze import router as analyze_router
from thati.routers.review import admin_router, blacklist_router, reports_router

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    analyze_limiter.configure(
        max_requests=settings.analyze_rate_limit,
        window_seconds=settings.analyze_rate_window_seconds,
    )
    ensure_database(settings.sqlite_path)
    yield


app = FastAPI(title="Thati AI", version="0.1.0", lifespan=lifespan)
app.include_router(analyze_router)
app.include_router(reports_router)
app.include_router(blacklist_router)
app.include_router(admin_router)


def _safe_error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": code})


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(
    _request: Request, _exc: ProviderUnavailableError
) -> JSONResponse:
    return _safe_error(503, "provider_unavailable")


@app.exception_handler(ProviderError)
async def provider_error_handler(_request: Request, _exc: ProviderError) -> JSONResponse:
    return _safe_error(502, "provider_error")


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("error", "request_failed"))
        return _safe_error(exc.status_code, code)
    return _safe_error(exc.status_code, "request_failed")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return _safe_error(422, "invalid_request")


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return _safe_error(500, "internal_error")


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    ready = database_is_ready(settings.sqlite_path)
    return {
        "status": "ok" if ready else "degraded",
        "mode": settings.app_mode,
        "ready": ready,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
