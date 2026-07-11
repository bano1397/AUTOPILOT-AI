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
from app.core.ratelimit import InMemoryRateLimiter
from app.domain.events import DocumentUploaded, DomainEvent
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.ingestion import IngestionService
from app.features.notifications.subscribers import register_notification_subscribers
from app.features.scheduler.jobs import register_scheduled_jobs
from app.features.scheduler.manager import SchedulerManager
from app.features.system.router import router as system_router
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.embeddings import JinaEmbeddingProvider, OllamaEmbeddingProvider
from app.infrastructure.llm import GroqLLMProvider, OllamaLLMProvider
from app.infrastructure.search import DuckDuckGoSearchProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import ChromaVectorStore, QdrantVectorStore
from app.platform.events import InProcessEventBus
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import discover_plugins
from app.workflows.checkpointer import WorkflowCheckpointer


def _build_llm(settings: Settings) -> LLMProvider:
    """Select the LLM provider from config (local Ollama or cloud Groq)."""
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
    """Select the embedding provider from config (local Ollama or cloud Jina)."""
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


def _build_vector_store(settings: Settings) -> VectorStoreProvider:
    """Select the vector store from config (local Chroma or cloud Qdrant)."""
    if settings.vector_store_provider == "qdrant":
        if not settings.qdrant_url:
            raise ValueError("VECTOR_STORE_PROVIDER=qdrant requires QDRANT_URL")
        return QdrantVectorStore(
            base_url=settings.qdrant_url,
            collection=settings.chroma_collection,
            dimension=settings.embedding_dim,
            api_key=settings.qdrant_api_key,
        )
    return ChromaVectorStore(
        base_url=settings.chroma_url, collection=settings.chroma_collection
    )


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
    app.state.storage = LocalStorageProvider(settings.documents_dir)
    app.state.embeddings = _build_embeddings(settings)
    app.state.vector_store = _build_vector_store(settings)
    app.state.llm = _build_llm(settings)
    app.state.search = DuckDuckGoSearchProvider()
    # Every LLM call goes through the recorder so it is audited (tokens, cost,
    # timing, errors) and emits CostRecorded.
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=event_bus)
    app.state.checkpointer = checkpointer
    app.state.rate_limiter = InMemoryRateLimiter()

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
