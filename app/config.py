from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "twstock-radar"
    database_url: str = "sqlite:///./radar.db"
    timezone: str = "Asia/Taipei"
    api_token: Optional[str] = None

    # After-close retry window (local time HH:MM)
    ingest_retry_times: str = "18:30,19:30,20:30"

    # Notifications
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_to: Optional[str] = None
    smtp_use_tls: bool = True

    # Default rule thresholds
    trust_top_k: int = 20
    trust_streak_days: int = 3
    trust_min_net_lots: float = 200.0
    alert_cooldown_days: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
