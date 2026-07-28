"""Application entry point.

``create_app`` is an application factory: it wires configuration, logging,
middleware, and routers into a fresh :class:`~fastapi.FastAPI` instance. Using a
factory (rather than only a module-level global) keeps the app fully isolated
and testable. A module-level ``app`` is also exposed for ASGI servers
(``uvicorn app.main:app``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware, SecurityHeadersMiddleware
from app.domain.events import DocumentUploaded, DomainEvent
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.storage import StorageProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.ingestion import IngestionService
from app.features.notifications.subscribers import register_notification_subscribers
from app.features.scheduler.jobs import register_scheduled_jobs
from app.features.scheduler.manager import SchedulerManager
from app.features.system.router import router as system_router
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.email import ImapEmailReader, SmtpEmailSender
from app.infrastructure.embeddings import (
    JinaEmbeddingProvider,
    OllamaEmbeddingProvider,
    StubEmbeddingProvider,
)
from app.infrastructure.llm import (
    GroqLLMProvider,
    OllamaLLMProvider,
    StubLLMProvider,
)
from app.infrastructure.search import DuckDuckGoSearchProvider
from app.infrastructure.storage import LocalStorageProvider, S3StorageProvider
from app.infrastructure.vectorstore import (
    ChromaVectorStore,
    InMemoryVectorStore,
    QdrantVectorStore,
)
from app.mcp import discover_mcp_tools
from app.platform.events import InProcessEventBus
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import discover_plugins
from app.workflows.checkpointer import WorkflowCheckpointer


def _build_llm(settings: Settings) -> LLMProvider:
    """Select the LLM provider from config (Ollama, Groq, or the stub)."""
    if settings.llm_provider == "stub":
        return StubLLMProvider()
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq requires GROQ_API_KEY")
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
        )
    return OllamaLLMProvider(base_url=settings.ollama_base_url, model=settings.llm_model)


def _build_embeddings(settings: Settings) -> EmbeddingProvider:
    """Select the embedding provider from config (Ollama, Jina, or the stub)."""
    if settings.embedding_provider == "stub":
        return StubEmbeddingProvider(dimensions=settings.embedding_dim)
    if settings.embedding_provider == "jina":
        if not settings.jina_api_key:
            raise ValueError("EMBEDDING_PROVIDER=jina requires JINA_API_KEY")
        return JinaEmbeddingProvider(
            api_key=settings.jina_api_key,
            model=settings.jina_model,
            dimensions=settings.embedding_dim,
        )
    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url, model=settings.embedding_model
    )


def _build_email_reader(settings: Settings) -> ImapEmailReader | None:
    """IMAP reader, or None when no mailbox is configured."""
    if not (settings.imap_host and settings.imap_username and settings.imap_password):
        return None
    return ImapEmailReader(
        host=settings.imap_host,
        port=settings.imap_port,
        username=settings.imap_username,
        password=settings.imap_password,
        mailbox=settings.imap_mailbox,
        use_ssl=settings.imap_use_ssl,
    )


def _build_email_sender(settings: Settings) -> SmtpEmailSender | None:
    """SMTP sender, or None when no outbound mail is configured."""
    if not (settings.smtp_host and settings.smtp_from):
        return None
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_from,
        username=settings.smtp_username,
        password=settings.smtp_password,
    )


def _build_storage(settings: Settings) -> StorageProvider:
    """Select file storage from config (local disk or an S3-compatible bucket)."""
    if settings.storage_provider == "s3":
        missing = [
            name
            for name, value in (
                ("S3_BUCKET", settings.s3_bucket),
                ("S3_ENDPOINT_URL", settings.s3_endpoint_url),
                ("S3_ACCESS_KEY_ID", settings.s3_access_key_id),
                ("S3_SECRET_ACCESS_KEY", settings.s3_secret_access_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "STORAGE_PROVIDER=s3 requires " + ", ".join(missing)
            )
        # The checks above narrow these to str for the type checker.
        assert settings.s3_bucket and settings.s3_endpoint_url  # noqa: S101
        assert settings.s3_access_key_id and settings.s3_secret_access_key  # noqa: S101
        return S3StorageProvider(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            region=settings.s3_region,
        )
    return LocalStorageProvider(settings.documents_dir)


def _build_vector_store(settings: Settings, collection: str) -> VectorStoreProvider:
    """Select the vector store from config (Chroma, Qdrant, or in-process).

    ``collection`` names the namespace: document chunks and long-term memory
    each get their own, so neither can contaminate the other's search results.
    """
    if settings.vector_store_provider == "memory":
        return InMemoryVectorStore()
    if settings.vector_store_provider == "qdrant":
        if not settings.qdrant_url:
            raise ValueError("VECTOR_STORE_PROVIDER=qdrant requires QDRANT_URL")
        return QdrantVectorStore(
            base_url=settings.qdrant_url,
            collection=collection,
            dimension=settings.embedding_dim,
            api_key=settings.qdrant_api_key,
        )
    return ChromaVectorStore(base_url=settings.chroma_url, collection=collection)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = settings or get_settings()
    setup_logging(settings)
    logger = get_logger("app.main")

    # Application-scoped services. The event bus decouples producers from
    # consumers; the database provider owns the async engine/session factory.
    event_bus = InProcessEventBus()
    db = SqlAlchemyDatabaseProvider(database_url=settings.database_url, echo=settings.db_echo)
    checkpointer = WorkflowCheckpointer(settings.checkpoint_db_path)
    scheduler = SchedulerManager()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Import plugin modules so their registration decorators execute.
        discovered = discover_plugins()
        # Remote MCP tools join the same registry as native ones. Config-gated
        # and failure-isolated: an unreachable server never blocks boot.
        mcp_summary = await discover_mcp_tools(settings.mcp_servers)
        # Workflow pause/resume state (LangGraph checkpoints).
        await checkpointer.start()
        # Recurring jobs need the running event loop, hence started here.
        scheduler.start()
        logger.info(
            "app.startup",
            extra={
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment.value,
                "plugins_discovered": discovered,
                "mcp_servers": mcp_summary["servers"],
                "mcp_tools": mcp_summary["tools"],
            },
        )
        yield
        scheduler.shutdown()
        await checkpointer.stop()
        await db.dispose()
        logger.info("app.shutdown")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.event_bus = event_bus
    app.state.db = db
    app.state.storage = _build_storage(settings)
    app.state.embeddings = _build_embeddings(settings)
    app.state.vector_store = _build_vector_store(settings, settings.chroma_collection)
    app.state.memory_vector_store = _build_vector_store(
        settings, settings.memory_collection
    )
    app.state.llm = _build_llm(settings)
    app.state.search = DuckDuckGoSearchProvider()
    app.state.email_reader = _build_email_reader(settings)
    app.state.email_sender = _build_email_sender(settings)
    # Every LLM call goes through the recorder so it is audited (tokens, cost,
    # timing, errors) and emits CostRecorded.
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=event_bus)
    app.state.checkpointer = checkpointer

    # Event-driven ingestion: providers are resolved from app.state at event
    # time, so swapping them (tests, alternative backends) needs no re-wiring.
    async def _on_document_uploaded(event: DomainEvent) -> None:
        if isinstance(event, DocumentUploaded):
            service = IngestionService(
                db=app.state.db,
                storage=app.state.storage,
                embeddings=app.state.embeddings,
                vector_store=app.state.vector_store,
                bus=event_bus,
            )
            await service.ingest(UUID(event.document_id))

    event_bus.subscribe(DocumentUploaded, _on_document_uploaded)

    # Event-driven notifications: approvals, failures, and indexing completions
    # fan out to every configured channel (in-app always; Telegram/SMTP by env).
    register_notification_subscribers(event_bus, lambda: app.state.db)

    # Recurring jobs (daily digest); dependencies resolve at run time.
    app.state.scheduler = scheduler
    register_scheduled_jobs(scheduler, lambda: app.state.db)

    # Correlation id must be established before other middleware/handlers run.
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Unversioned system endpoints + versioned API surface.
    app.include_router(system_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Consistent error envelope for all endpoints.
    register_exception_handlers(app)

    return app


app = create_app()
