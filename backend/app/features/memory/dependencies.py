"""Dependency providers for the long-term memory feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_db_session,
    get_embeddings,
    get_memory_vector_store,
)
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.memory.service import LongTermMemoryService


def get_memory_service(
    session: AsyncSession = Depends(get_db_session),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
    vector_store: VectorStoreProvider = Depends(get_memory_vector_store),
) -> LongTermMemoryService:
    return LongTermMemoryService(session, embeddings, vector_store)
