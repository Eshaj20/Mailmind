from functools import lru_cache
import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Central app settings loaded from environment variables or .env.
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
    gmail_scopes: str = "openid email profile https://www.googleapis.com/auth/gmail.modify"
    gmail_initial_sync_max_results: int = 25
    gmail_sync_query: str = "newer_than:30d"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    sync_job_max_attempts: int = 3
    api_rate_limit_per_minute: int = 120
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_input_cost_per_1m_tokens: float = 0.0
    openai_output_cost_per_1m_tokens: float = 0.0
    # Search knobs: local deterministic embeddings use the same contract as a future OpenAI embedding provider.
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 64
    search_rrf_k: int = 60  # Larger k softens rank differences when merging keyword/vector results.
    classification_rule_confidence_threshold: float = 0.75
    classification_batch_limit: int = 200
    spam_score_threshold: float = 0.7
    spam_high_risk_threshold: float = 0.85
    spam_model_path: str = ""
    spam_model_version: str = "pretrained-spam-v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Hosted Postgres providers often expose postgres:// or postgresql:// URLs.
        # Normalize them to the psycopg driver URL SQLAlchemy uses locally.
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

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