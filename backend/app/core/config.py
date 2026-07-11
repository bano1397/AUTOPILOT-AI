"""Application configuration.

All environment-specific values are loaded here from environment variables
(optionally sourced from a ``.env`` file). No configuration value is hardcoded
elsewhere in the codebase; modules depend on :func:`get_settings` instead.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment the application is running in."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(str, Enum):
    """Log output rendering format."""

    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    """Typed application settings.

    Values are read from environment variables (case-insensitive). A ``.env``
    file at the backend root or repository root is loaded automatically when
    present, which is convenient for local development.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "AutoPilot AI"
    app_version: str = "0.1.0"
    environment: Environment = Environment.LOCAL
    debug: bool = False

    # --- API --------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"  # noqa: S104 - binding to all interfaces is intended in containers
    port: int = 8000

    # --- CORS -------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g. "http://localhost:3000".
    # NoDecode: without it pydantic-settings JSON-decodes list-typed env values
    # before validators run, so a plain "http://..." string raises SettingsError.
    # 3001 is included because `next dev` falls back to it when 3000 is taken.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"]
    )

    # --- Database ---------------------------------------------------------
    # Async SQLAlchemy URL. SQLite by default; swap to
    # postgresql+asyncpg://... for production without code changes.
    database_url: str = "sqlite+aiosqlite:///./autopilot.db"
    db_echo: bool = False

    # --- Security / JWT ---------------------------------------------------
    # MUST be overridden in every non-local environment via JWT_SECRET_KEY.
    # Default is >= 32 bytes to satisfy HS256 key-length recommendations.
    jwt_secret_key: str = "change-me-in-production-set-a-secure-random-secret"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    # Per-IP sliding-window limit on login/register/refresh.
    auth_rate_limit_per_minute: int = 10

    # --- Documents / file storage ------------------------------------------
    # Base directory for uploaded files. Outside the webroot; in Docker this is
    # the mounted `documents` volume.
    documents_dir: str = "./documents"
    max_upload_size_mb: int = 25

    # --- RAG / ingestion -----------------------------------------------------
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # --- AI providers --------------------------------------------------------
    # Which implementation backs each port. Defaults keep everything local
    # (Ollama + Chroma); the cloud values (groq / jina / qdrant) are selected by
    # env for a free managed deployment — no code change required.
    llm_provider: str = "ollama"  # ollama | groq
    embedding_provider: str = "ollama"  # ollama | jina
    vector_store_provider: str = "chroma"  # chroma | qdrant
    # Vector dimension of the embedding model; sizes the Qdrant collection.
    # nomic-embed-text and jina-embeddings-v3 (via `dimensions`) are both 768.
    embedding_dim: int = 768

    # Local (Ollama + Chroma)
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "llama3"
    chroma_url: str = "http://localhost:8001"
    chroma_collection: str = "autopilot_documents"

    # Cloud LLM (Groq — OpenAI-compatible, free tier)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Cloud embeddings (Jina AI — free tier)
    jina_api_key: str | None = None
    jina_model: str = "jina-embeddings-v3"

    # Cloud vector store (Qdrant — free managed tier)
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None

    # --- Workflows -------------------------------------------------------
    # SQLite file backing LangGraph checkpoints (pause/resume state).
    checkpoint_db_path: str = "./workflow_checkpoints.db"

    # --- Scheduler ---------------------------------------------------------
    # Hour (UTC) at which the daily digest job runs.
    digest_hour: int = 8

    # --- Notifications (optional channels; in-app is always on) -----------
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    # --- Logging ----------------------------------------------------------
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow CORS origins to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Uppercase the log level so lowercase env values are accepted."""
        return value.upper() if isinstance(value, str) else value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.environment == Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
