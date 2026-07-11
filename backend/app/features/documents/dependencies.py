"""Dependency providers for the documents feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_db_session,
    get_event_bus,
    get_storage,
    get_vector_store,
)
from app.domain.interfaces.event_bus import EventBus
from app.domain.interfaces.storage import StorageProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.service import DocumentService


def get_document_service(
    session: AsyncSession = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage),
    event_bus: EventBus = Depends(get_event_bus),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
) -> DocumentService:
    return DocumentService(session, storage, event_bus, vector_store)
