"""Vector-store interface (port).

Stores chunk embeddings alongside their full text and metadata, and answers
similarity queries. The default implementation targets ChromaDB; any vector
database can be substituted behind this contract (blueprint §5, provider #3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class VectorMatch:
    """One similarity-search result."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: float = 0.0


class VectorStoreProvider(Protocol):
    """Contract for vector storage and similarity search."""

    async def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        """Insert or replace vectors with their source text and metadata."""
        ...

    async def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return the ``top_k`` most similar entries, optionally filtered."""
        ...

    async def delete(self, ids: Sequence[str]) -> None:
        """Remove the given vector ids (missing ids are ignored)."""
        ...
