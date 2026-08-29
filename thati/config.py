from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AppMode = Literal["mock", "live"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_mode: AppMode = Field(default="mock", alias="APP_MODE")
    sqlite_path: Path = Field(default=Path("data/thati.db"), alias="SQLITE_PATH")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.7-flash", alias="GEMINI_MODEL")
    gemini_timeout_ms: int = Field(default=60000, alias="GEMINI_TIMEOUT_MS")
    transcription_model: str = Field(
        default="gemini-3.5-transcribe",
        alias="TRANSCRIPTION_MODEL",
    )
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")
    analyze_max_chars: int = Field(default=8000, alias="ANALYZE_MAX_CHARS")
    analyze_rate_limit: int = Field(default=30, alias="ANALYZE_RATE_LIMIT")
    analyze_rate_window_seconds: float = Field(
        default=60.0,
        alias="ANALYZE_RATE_WINDOW_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
