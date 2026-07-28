"""Cross-cutting FastAPI dependencies.

Provides access to application-scoped services (such as the event bus) that live
on ``app.state``. Feature-specific dependencies live in each feature's
``dependencies.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.event_bus import EventBus
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.search import SearchProvider
from app.domain.interfaces.storage import StorageProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.platform.observability.recorder import AiExecutionRecorder


def get_event_bus(request: Request) -> EventBus:
    """Return the application-scoped event bus."""
    return cast(EventBus, request.app.state.event_bus)


def get_storage(request: Request) -> StorageProvider:
    """Return the application-scoped file-storage provider."""
    return cast(StorageProvider, request.app.state.storage)


def get_embeddings(request: Request) -> EmbeddingProvider:
    """Return the application-scoped embedding provider."""
    return cast(EmbeddingProvider, request.app.state.embeddings)


def get_vector_store(request: Request) -> VectorStoreProvider:
    """Return the application-scoped vector-store provider."""
    return cast(VectorStoreProvider, request.app.state.vector_store)


def get_memory_vector_store(request: Request) -> VectorStoreProvider:
    """Return the vector store backing long-term memory.

    A separate namespace from :func:`get_vector_store`, which serves document
    chunks; see ``app.features.memory.service`` for why they are not shared.
    """
    return cast(VectorStoreProvider, request.app.state.memory_vector_store)


def get_llm(request: Request) -> LLMProvider:
    """Return the application-scoped LLM provider."""
    return cast(LLMProvider, request.app.state.llm)


def get_search(request: Request) -> SearchProvider:
    """Return the application-scoped web search provider."""
    return cast(SearchProvider, request.app.state.search)


def get_ai_recorder(request: Request) -> AiExecutionRecorder:
    """Return the application-scoped AI execution recorder."""
    return cast(AiExecutionRecorder, request.app.state.ai_recorder)


def get_database(request: Request) -> DatabaseProvider:
    """Return the application-scoped database provider."""
    return cast(DatabaseProvider, request.app.state.db)


def get_checkpointer(request: Request) -> object | None:
    """Return the started LangGraph checkpoint saver, if available.

    ``None`` outside the app lifespan (e.g. plain unit contexts); graphs then
    compile without persistence and the approval gate cannot pause.
    """
    checkpointer = getattr(request.app.state, "checkpointer", None)
    return getattr(checkpointer, "saver", None)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a database session scoped to the request."""
    database = get_database(request)
    async with database.session() as session:
        yield session
