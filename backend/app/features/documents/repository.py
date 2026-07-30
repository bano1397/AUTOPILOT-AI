"""Data-access repository for documents.

Every query is owner-scoped: a document belonging to another user is
indistinguishable from a missing one (no existence leak).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, or_, select
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

    async def search_chunk_text(
        self, user_id: UUID, terms: Sequence[str], *, limit: int
    ) -> list[tuple[DocumentChunk, str]]:
        """Owner-scoped chunks whose text contains any of ``terms``.

        This is a *candidate* prefilter, not the ranking: BM25 scores what comes
        back (see ``app.platform.rag.keyword``). Splitting it this way keeps the
        scoring portable — SQLite and Postgres disagree entirely on full-text
        search, and neither dialect's implementation would be reachable from a
        plain SQLAlchemy query without dialect-specific DDL.

        The cost is a ``LIKE`` scan with no index, so this is linear in the
        number of chunks. Fine for the thousands a workspace of documents
        produces; the point at which it stops being fine is the point at which
        the prefilter should move to Postgres ``tsvector`` behind this same
        method.

        Chunks written before the full-text column existed have ``content``
        NULL and cannot match — they stay vector-searchable, and re-indexing
        the document restores them.
        """
        if not terms:
            return []
        # Terms come from `tokenize()`, so they are alphanumeric and cannot
        # carry LIKE wildcards.
        result = await self._session.execute(
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                DocumentChunk.content.is_not(None),
                or_(*[DocumentChunk.content.ilike(f"%{term}%") for term in terms]),
            )
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def chunk_vector_ids(self, document_id: UUID) -> list[str]:
        result = await self._session.execute(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.vector_id.is_not(None),
            )
        )
        return [str(vector_id) for vector_id in result.scalars().all()]
