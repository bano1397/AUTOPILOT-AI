"""Document use-cases: secure upload, listing, retrieval, re-indexing, deletion."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.domain.events import DocumentReindexRequested, DocumentUploaded
from app.domain.interfaces.event_bus import EventBus
from app.domain.interfaces.storage import StorageProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.models import Document
from app.features.documents.repository import DocumentRepository
from app.features.documents.validation import validate_upload
from app.features.users.models import User

logger = get_logger("app.features.documents")


class DocumentService:
    """Document management use-cases; owns the transaction commit."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider,
        event_bus: EventBus,
        vector_store: VectorStoreProvider,
    ) -> None:
        self._session = session
        self._storage = storage
        self._event_bus = event_bus
        self._vector_store = vector_store
        self._documents = DocumentRepository(session)

    async def upload(
        self, user: User, *, filename: str | None, content: bytes, declared_mime: str | None
    ) -> Document:
        """Validate, store, and record an uploaded file; emit ``DocumentUploaded``."""
        settings = get_settings()
        validated = validate_upload(
            filename,
            content,
            declared_mime,
            max_bytes=settings.max_upload_size_mb * 1024 * 1024,
            ocr_enabled=settings.ocr_enabled,
        )

        storage_path = await self._storage.save(content, suffix=validated.suffix)
        document = Document(
            user_id=user.id,
            filename=validated.safe_filename,
            mime_type=validated.canonical_mime,
            size_bytes=len(content),
            storage_path=storage_path,
        )
        await self._documents.add(document)
        await self._session.commit()

        # The ingestion pipeline (M2 sub-steps 2+) subscribes to this event.
        await self._event_bus.publish(
            DocumentUploaded(document_id=str(document.id), user_id=str(user.id))
        )
        return document

    async def list_documents(
        self, user: User, pagination: PaginationParams
    ) -> tuple[Sequence[Document], int]:
        items = await self._documents.list_for_user(
            user.id, offset=pagination.offset, limit=pagination.limit
        )
        total = await self._documents.count_for_user(user.id)
        return items, total

    async def get_document(self, user: User, document_id: UUID) -> Document:
        document = await self._documents.get_for_user(document_id, user.id)
        if document is None:
            raise NotFoundError("Document not found")
        return document

    async def reindex_document(self, user: User, document_id: UUID) -> Document:
        """Ask for the document to be ingested again; emit the request event.

        Ownership is checked here so the handler can trust the id. The rebuild
        itself is the ingestion pipeline's job -- this method only asks.
        """
        document = await self.get_document(user, document_id)
        await self._event_bus.publish(
            DocumentReindexRequested(
                document_id=str(document.id), user_id=str(user.id)
            )
        )
        await self._session.refresh(document)
        return document

    async def delete_document(self, user: User, document_id: UUID) -> None:
        """Delete the records first (committed), then file + vectors best-effort.

        The database is the source of truth: an orphaned file or vector is
        harmless and cleanable, while a surviving DB row pointing at deleted
        content would be a bug — hence this ordering.
        """
        document = await self.get_document(user, document_id)
        storage_path = document.storage_path
        vector_ids = await self._documents.chunk_vector_ids(document_id)
        await self._documents.delete(document)
        await self._session.commit()

        try:
            await self._storage.delete(storage_path)
        except OSError:
            logger.warning(
                "document.file_delete_failed", extra={"storage_path": storage_path}
            )
        if vector_ids:
            try:
                await self._vector_store.delete(vector_ids)
            except Exception:
                logger.warning(
                    "document.vector_delete_failed",
                    extra={"document_id": str(document_id), "count": len(vector_ids)},
                )
