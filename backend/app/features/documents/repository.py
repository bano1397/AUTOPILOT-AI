"""Data-access repository for documents.

Every query is owner-scoped: a document belonging to another user is
indistinguishable from a missing one (no existence leak).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.documents.models import Document, DocumentChunk


class DocumentRepository:
    """Persistence operations for :class:`Document`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        """System-level lookup (no owner scoping) — for the ingestion pipeline."""
        return await self._session.get(Document, document_id)

    async def get_for_user(self, document_id: UUID, user_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> Sequence[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Document).where(Document.user_id == user_id)
        )
        return int(result.scalar_one())

    async def delete(self, document: Document) -> None:
        # Chunks are removed explicitly: SQLite does not enforce FK cascades by
        # default, and async ORM cascade would require lazy-loading the chunks.
        await self.delete_chunks(document.id)
        await self._session.delete(document)
        await self._session.flush()

    # --- Chunks -------------------------------------------------------------

    async def add_chunks(self, chunks: Sequence[DocumentChunk]) -> None:
        self._session.add_all(chunks)
        await self._session.flush()

    async def count_chunks(self, document_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        return int(result.scalar_one())

    async def delete_chunks(self, document_id: UUID) -> None:
        await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

    async def chunk_vector_ids(self, document_id: UUID) -> list[str]:
        result = await self._session.execute(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.vector_id.is_not(None),
            )
        )
        return [str(vector_id) for vector_id in result.scalars().all()]
