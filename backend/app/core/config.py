from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_ROOT / 'nmc.db'}"
    redis_url: str = ""
    jwt_private_key_path: str = str(BACKEND_ROOT / "keys" / "jwt_private.pem")
    jwt_public_key_path: str = str(BACKEND_ROOT / "keys" / "jwt_public.pem")
    jwt_key_id: str = "k1"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    badge_token_enc_key: str = ""
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    feature_google_signin: bool = False
    feature_apple_signin: bool = False
    ai_enabled: bool = True
    ai_provider: str = "groq"
    ai_model: str = "openai/gpt-oss-20b"
    ai_api_key: str = ""
    groq_api_key: str = ""
    ai_max_output_tokens: int = 400
    ai_timeout_seconds: int = 15
    ai_history_messages: int = 8
    ai_rate_limit_per_min: int = 10
    ai_rate_limit_per_day: int = 100
    ai_context_ttl_seconds: int = 60
    fcm_server_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "congress@example.com"
    s3_bucket: str = ""
    s3_region: str = "me-central-1"
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
