from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SETTINGS_ENV_FILE,
        env_prefix="TRACEQA_",
        extra="ignore",
    )

    app_name: str = "TraceQA API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://traceqa:traceqa@localhost:5432/traceqa"
    )
    db_echo: bool = False
    test_logs_directory: Path = Path("test-logs")
    automatic_ingestion_enabled: bool = True
    ingestion_max_files: int = Field(default=100, ge=1, le=1000)
    ingestion_max_file_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
    )
    ingestion_max_markdown_chars: int = Field(
        default=1_000_000,
        ge=1,
    )
    llm_model: str = "gemini/gemini-2.5-flash"
    llm_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_request_timeout_seconds: float = Field(default=600, ge=10, le=900)
    llm_max_input_chars: int = Field(default=500_000, ge=10_000, le=500_000)
    llm_api_key: SecretStr | None = None
    github_token: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None
    github_diff_max_chars: int = Field(default=500_000, ge=1)
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
