"""Long-term memory use-cases: remember, recall, list, forget.

Level 3 of the memory architecture (blueprint §16). Durable facts live in the
``memory_entries`` table and are indexed into a **separate vector namespace**
from document chunks.

Why a separate namespace rather than a ``kind`` metadata filter on the shared
collection: document vectors written before this feature existed carry no such
field, so a filter would have silently dropped every previously-indexed
document from RAG results. A distinct collection cannot regress the document
path at all, and it keeps the two lifecycles independently clearable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.memory.models import MemoryEntry, MemoryKind
from app.features.memory.repository import MemoryRepository

logger = get_logger("app.features.memory")


@dataclass(frozen=True)
class Recollection:
    """One recalled memory, with its similarity distance."""

    entry: MemoryEntry
    distance: float

    @property
    def relevance(self) -> float:
        """Similarity on a 0–1 scale, matching the RAG match convention."""
        return max(0.0, 1.0 - self.distance)


class LongTermMemoryService:
    """Durable facts, semantically recallable."""

    def __init__(
        self,
        session: AsyncSession,
        embeddings: EmbeddingProvider,
        vector_store: VectorStoreProvider,
    ) -> None:
        self._session = session
        self._repo = MemoryRepository(session)
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def remember(
        self,
        user_id: UUID,
        content: str,
        *,
        kind: MemoryKind = MemoryKind.FACT,
        source: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> MemoryEntry:
        """Persist a durable fact and index it for semantic recall.

        The row is committed even when embedding fails: losing the fact
        entirely is worse than holding one that is listable but not yet
        semantically recallable. Callers can tell the difference —
        ``vector_id`` is ``None`` on an unindexed entry.
        """
        entry = await self._repo.add(
            MemoryEntry(
                user_id=user_id,
                content=content,
                kind=kind.value,
                source=source,
                meta=dict(meta) if meta else None,
            )
        )
        # Flush assigned the row id, which doubles as the vector id.
        vector_id = str(entry.id)
        try:
            vectors = await self._embeddings.embed([content])
            (embedding,) = vectors
            await self._vector_store.upsert(
                ids=[vector_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[
                    {
                        "user_id": str(user_id),
                        "kind": kind.value,
                        "source": source or "",
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 - degradation is deliberate
            logger.warning(
                "memory.index_failed",
                extra={"entry_id": vector_id, "error": str(exc)},
            )
        else:
            entry.vector_id = vector_id

        await self._session.commit()
        await self._session.refresh(entry)
        return entry

    async def recall(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[Recollection]:
        """Return the owner's most similar durable facts for ``query``.

        Raises :class:`UpstreamServiceError` when the embedding provider or the
        vector store is unavailable — the same contract as document retrieval,
        so callers that want to degrade do so explicitly rather than silently.
        """
        try:
            vectors = await self._embeddings.embed([query])
            (embedding,) = vectors
        except Exception as exc:
            logger.warning("memory.embedding_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Embedding provider is unavailable") from exc

        try:
            matches = await self._vector_store.query(
                embedding, top_k=top_k, where={"user_id": str(user_id)}
            )
        except Exception as exc:
            logger.warning("memory.vector_query_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Vector store is unavailable") from exc

        if not matches:
            return []

        # Hydrate hits back into rows. A vector whose row is gone is skipped
        # rather than surfaced: the row is the source of truth, and an orphan
        # vector (a failed delete, a restored backup) must not resurrect a
        # forgotten fact.
        entry_ids: list[UUID] = []
        distance_by_id: dict[UUID, float] = {}
        for match in matches:
            try:
                entry_id = UUID(match.id)
            except ValueError:
                logger.warning("memory.unparsable_vector_id", extra={"id": match.id})
                continue
            entry_ids.append(entry_id)
            distance_by_id[entry_id] = match.distance

        rows = {row.id: row for row in await self._repo.get_many(entry_ids)}
        return [
            Recollection(entry=rows[entry_id], distance=distance_by_id[entry_id])
            for entry_id in entry_ids
            if entry_id in rows
        ]

    async def list_entries(
        self, user_id: UUID, pagination: PaginationParams, *, kind: MemoryKind | None = None
    ) -> tuple[Sequence[MemoryEntry], int]:
        """Page the owner's memories, newest first."""
        kind_value = kind.value if kind else None
        items = await self._repo.list_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit, kind=kind_value
        )
        total = await self._repo.count_for_user(user_id, kind=kind_value)
        return items, total

    async def forget(self, user_id: UUID, entry_id: UUID) -> None:
        """Delete a memory and its vector.

        The row is deleted even if the vector delete fails; ``recall`` skips
        vectors with no surviving row, so a leaked vector cannot resurface the
        fact. The reverse order would risk the opposite.
        """
        entry = await self._repo.get(entry_id)
        if entry is None or entry.user_id != user_id:
            raise NotFoundError("Memory entry not found")

        vector_id = entry.vector_id
        await self._repo.delete(entry)
        await self._session.commit()

        if vector_id:
            try:
                await self._vector_store.delete([vector_id])
            except Exception as exc:  # noqa: BLE001 - the row is already gone
                logger.warning(
                    "memory.vector_delete_failed",
                    extra={"entry_id": str(entry_id), "error": str(exc)},
                )
