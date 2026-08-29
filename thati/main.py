from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from thati.config import get_settings
from thati.db import database_is_ready, ensure_database

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    ensure_database(settings.sqlite_path)
    yield


app = FastAPI(title="Thati AI", version="0.1.0", lifespan=lifespan)


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
