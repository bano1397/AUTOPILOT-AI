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

    # --- Security ----------------------------------------------------------
    # There is no authentication (docs/COMPLETION_PLAN.md §3), so there are no
    # JWT, session, or auth rate-limit settings. Security headers are still
    # applied by middleware, and HSTS is enabled in production only.

    # --- Documents / file storage ------------------------------------------
    # Which implementation backs the StorageProvider port. `local` keeps files
    # on disk (ephemeral on free PaaS tiers); `s3` puts them in any
    # S3-compatible bucket (Cloudflare R2, AWS S3, MinIO) so they survive
    # restarts.
    storage_provider: str = "local"  # local | s3
    # Base directory for uploaded files when storage_provider=local. Outside the
    # webroot; in Docker this is the mounted `documents` volume.
    documents_dir: str = "./documents"
    max_upload_size_mb: int = 25

    # S3-compatible object storage (used when storage_provider=s3).
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    # R2 accepts the literal "auto"; AWS requires a real region name.
    s3_region: str = "auto"

    # --- RAG / ingestion -----------------------------------------------------
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Hybrid retrieval (blueprint §17): vector + BM25 keyword, fused with RRF.
    # Disable to fall back to vector-only retrieval.
    rag_hybrid_enabled: bool = True
    # How many keyword candidates the SQL prefilter may return before BM25
    # scores them. Caps an unindexed LIKE scan; raising it trades query latency
    # for recall on large corpora.
    rag_keyword_candidates: int = 200
    # Token budget for retrieved context in a grounded answer. Counted with an
    # estimator, not a tokenizer -- see app/platform/rag/compression.py.
    rag_context_budget_tokens: int = 2000

    # OCR for scanned documents. Off by default: it needs the Tesseract binary,
    # which is a system package rather than a Python dependency.
    ocr_enabled: bool = False
    ocr_languages: str = "eng"

    # --- AI providers --------------------------------------------------------
    # Which implementation backs each port. Defaults keep everything local
    # (Ollama + Chroma); the cloud values (groq / jina / qdrant) are selected by
    # env for a free managed deployment — no code change required.
    # The stub / memory values run the whole platform with no model server and
    # no network, for the demo stack and the e2e suite. They produce fixed,
    # unintelligent output — never select them in a deployment meant to be
    # useful. See app/infrastructure/llm/stub.py.
    llm_provider: str = "ollama"  # ollama | groq | stub
    embedding_provider: str = "ollama"  # ollama | jina | stub
    vector_store_provider: str = "chroma"  # chroma | qdrant | memory
    # Vector dimension of the embedding model; sizes the Qdrant collection.
    # nomic-embed-text and jina-embeddings-v3 (via `dimensions`) are both 768.
    embedding_dim: int = 768

    # Local (Ollama + Chroma)
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "llama3"
    chroma_url: str = "http://localhost:8001"
    chroma_collection: str = "autopilot_documents"
    # Long-term memory indexes into its own collection rather than sharing the
    # document one: pre-existing document vectors carry no discriminating
    # metadata, so a shared collection could not be filtered without silently
    # dropping them from RAG results. Applies to Qdrant too, despite the name.
    memory_collection: str = "autopilot_memory"

    # Cloud LLM (Groq — OpenAI-compatible, free tier)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Cloud embeddings (Jina AI — free tier)
    jina_api_key: str | None = None
    jina_model: str = "jina-embeddings-v3"

    # Reranking. `none` is a genuine pass-through, not a degraded reranker:
    # there is no honest local cross-encoder, so the stage is simply absent
    # unless configured. `jina` reuses JINA_API_KEY.
    rerank_provider: str = "none"  # none | jina
    jina_rerank_model: str = "jina-reranker-v2-base-multilingual"
    # Candidates handed to the reranker; it returns the best `top_k` of these.
    # Reranking is only worth its latency with more candidates than answers.
    rerank_candidates: int = 20

    # Cloud vector store (Qdrant — free managed tier)
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None

    # --- Calendar -----------------------------------------------------------
    # `local` stores events in this platform's own database, so scheduling
    # works with no external account. `google` selects the adapter seam, which
    # has no OAuth flow yet and fails loudly rather than returning an empty
    # calendar -- see app/infrastructure/calendar/google.py.
    calendar_provider: str = "local"  # local | google

    # --- Email (IMAP in, SMTP out) ----------------------------------------
    # Mailbox reading is enabled when host + username + password are all set;
    # sending reuses the SMTP_* settings below. Both are optional: without them
    # the emails API still serves reads and returns a clear 502 on sync/send.
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = None
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # --- MCP (Model Context Protocol) -------------------------------------
    # JSON array of servers to consume tools from. This is the allow-list: only
    # servers named here are ever contacted. Example:
    #   [{"name": "files", "transport": "stdio",
    #     "command": "mcp-server-filesystem", "args": ["/data"]}]
    #   [{"name": "remote", "transport": "http", "url": "https://host/mcp"}]
    mcp_servers: str | None = None

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
