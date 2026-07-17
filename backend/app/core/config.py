from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Hermes Subscription Manager"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://hermes:change-me@localhost:5432/hermes"
    scheduler_heartbeat_seconds: int = Field(default=60, ge=5, le=3600)


@lru_cache
def get_settings() -> Settings:
    return Settings()
