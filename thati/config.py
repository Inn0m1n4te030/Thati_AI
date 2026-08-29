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
    transcription_model: str = Field(
        default="gemini-3.5-transcribe",
        alias="TRANSCRIPTION_MODEL",
    )
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
