"""In-process vector store (``VECTOR_STORE_PROVIDER=memory``).

Cosine similarity over a dict. No server, no persistence — the index dies with
the process. Completes the zero-dependency stack alongside the stub LLM and
stub embeddings, so the demo and the end-to-end suite can run with nothing but
the backend itself.

Correct but linear: every query scores every vector. Fine for the hundreds of
chunks a demo or an e2e run produces; useless at real corpus sizes. Use Chroma
or Qdrant for anything that must survive a restart or exceed a few thousand
vectors.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.interfaces.vector_store import VectorMatch
from app.platform.registry import register_provider


@dataclass
class _Entry:
    embedding: list[float]
    document: str
    metadata: dict[str, Any]


@register_provider(kind="vectorstore", name="memory")
class InMemoryVectorStore:
    """Exhaustive cosine search over an in-process dict."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    async def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        for position, vector_id in enumerate(ids):
            self._entries[vector_id] = _Entry(
                embedding=list(embeddings[position]),
                document=documents[position],
                metadata=dict(metadatas[position]),
            )

    async def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        query_vector = list(embedding)
        scored: list[tuple[float, str, _Entry]] = []
        for vector_id, entry in self._entries.items():
            if where and not all(
                entry.metadata.get(key) == value for key, value in where.items()
            ):
                continue
            scored.append((_cosine(query_vector, entry.embedding), vector_id, entry))

        # Highest similarity first; the port's contract is a distance, so the
        # score is inverted on the way out to match the Chroma/Qdrant paths.
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            VectorMatch(
                id=vector_id,
                text=entry.document,
                metadata=dict(entry.metadata),
                distance=1.0 - similarity,
            )
            for similarity, vector_id, entry in scored[:top_k]
        ]

    async def delete(self, ids: Sequence[str]) -> None:
        for vector_id in ids:
            self._entries.pop(vector_id, None)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity, 0.0 when either side is a zero vector."""
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
