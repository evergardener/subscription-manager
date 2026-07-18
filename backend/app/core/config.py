from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Hermes Subscription Manager"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://hermes:change-me@localhost:5432/hermes"
    scheduler_heartbeat_seconds: int = Field(default=60, ge=5, le=3600)
    session_absolute_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    cookie_secure: bool = False
    ntfy_base_url: str = "https://ntfy.sh"
    ntfy_topic: str = "replace-me"
    reminder_scan_days: int = Field(default=30, ge=1, le=366)
    reminder_grace_days: int = Field(default=3, ge=0, le=30)
    reminder_max_attempts: int = Field(default=5, ge=1, le=20)
    reminder_lease_seconds: int = Field(default=120, ge=30, le=3600)

    @model_validator(mode="after")
    def require_secure_production_cookie(self) -> "Settings":
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
