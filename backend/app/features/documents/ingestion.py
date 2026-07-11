"""Event-driven document ingestion pipeline.

Subscribes (via ``main.py``) to :class:`DocumentUploaded` and drives the status
lifecycle ``UPLOADED → PROCESSING → INDEXED | FAILED``:

    load document → read bytes from storage → extract text → chunk →
    persist chunks → embed → upsert vectors → fill vector ids

The service runs outside any HTTP request, so it opens its own session from the
:class:`DatabaseProvider` and re-reads content from the :class:`StorageProvider`
using only the IDs carried by the event (replay-safe). Chunk row UUIDs double as
vector ids, so the relational and vector stores share one key.
"""

from __future__ import annotations

from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.events import DocumentIndexed
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.event_bus import EventBus
from app.domain.interfaces.storage import StorageProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.models import Document, DocumentChunk, DocumentStatus
from app.features.documents.repository import DocumentRepository
from app.infrastructure.extraction import extractor_for
from app.platform.rag import TextChunker

logger = get_logger("app.features.documents.ingestion")

_PREVIEW_CHARS = 500


class IngestionService:
    """Processes one uploaded document end-to-end."""

    def __init__(
        self,
        db: DatabaseProvider,
        storage: StorageProvider,
        embeddings: EmbeddingProvider,
        vector_store: VectorStoreProvider,
        bus: EventBus | None = None,
    ) -> None:
        self._db = db
        self._storage = storage
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._bus = bus

    async def ingest(self, document_id: UUID) -> None:
        """Extract, chunk, and persist; record failures on the document row."""
        async with self._db.session() as session:
            repository = DocumentRepository(session)
            document = await repository.get_by_id(document_id)
            if document is None:
                logger.warning(
                    "ingestion.document_missing", extra={"document_id": str(document_id)}
                )
                return
            if document.status is not DocumentStatus.UPLOADED:
                # Idempotency guard: replayed/duplicate events are no-ops.
                logger.info(
                    "ingestion.skipped",
                    extra={"document_id": str(document_id), "status": document.status.value},
                )
                return

            document.status = DocumentStatus.PROCESSING
            await session.commit()

            try:
                chunks = await self._process(document, repository)
            except Exception as exc:
                await session.rollback()
                # Rollback expires loaded objects; refresh before touching
                # attributes (async sessions cannot lazy-refresh implicitly).
                await session.refresh(document)
                document.status = DocumentStatus.FAILED
                document.doc_metadata = {**document.doc_metadata, "error": str(exc)}
                await session.commit()
                logger.warning(
                    "ingestion.failed",
                    extra={"document_id": str(document_id), "error": str(exc)},
                )
                return

            document.status = DocumentStatus.INDEXED
            document.doc_metadata = {**document.doc_metadata, "chunk_count": len(chunks)}
            await session.commit()
            logger.info(
                "ingestion.completed",
                extra={"document_id": str(document_id), "chunks": len(chunks)},
            )

        if self._bus is not None:
            await self._bus.publish(
                DocumentIndexed(document_id=str(document_id), chunk_count=len(chunks))
            )

    async def _process(
        self, document: Document, repository: DocumentRepository
    ) -> list[DocumentChunk]:
        """The pipeline stages; raises on any failure."""
        content = await self._storage.get(document.storage_path)
        text = await extractor_for(document.mime_type).extract(content)

        settings = get_settings()
        chunker = TextChunker(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        chunks = chunker.split(text)
        if not chunks:
            raise ValueError("Document produced no text chunks")

        rows = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content_preview=chunk.text[:_PREVIEW_CHARS],
                chunk_metadata={"chars": len(chunk.text)},
            )
            for chunk in chunks
        ]
        # Flush assigns the row UUIDs, which double as the vector ids.
        await repository.add_chunks(rows)

        vectors = await self._embeddings.embed([chunk.text for chunk in chunks])
        vector_ids = [str(row.id) for row in rows]
        await self._vector_store.upsert(
            ids=vector_ids,
            embeddings=vectors,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "document_id": str(document.id),
                    "user_id": str(document.user_id),
                    "chunk_index": chunk.index,
                    "filename": document.filename,
                }
                for chunk in chunks
            ],
        )
        # The upsert is the last I/O before commit: on failure above, the DB
        # rollback discards the chunk rows and no vectors have been written.
        for row, vector_id in zip(rows, vector_ids, strict=True):
            row.vector_id = vector_id
        return rows
