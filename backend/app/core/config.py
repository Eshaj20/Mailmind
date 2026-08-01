from functools import lru_cache
import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "MailMind"
    api_v1_prefix: str = "/api/v1"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://mailmind:mailmind@postgres:5432/mailmind"
    secret_key: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/gmail/oauth/callback"
    gmail_scopes: str = "openid email profile https://www.googleapis.com/auth/gmail.readonly"
    gmail_initial_sync_max_results: int = 25
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    sync_job_max_attempts: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip().startswith("["):
            parsed = json.loads(self.cors_origins)
            return [origin.strip() for origin in parsed if origin.strip()]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gmail_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.gmail_scopes.split() if scope.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
