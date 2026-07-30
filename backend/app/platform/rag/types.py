"""The unit passed between RAG pipeline stages.

Retrieval → fusion → reranking → compression all hand each other the same
shape, so a stage can be reordered or removed without touching its neighbours.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace


class RetrievalSource(str, enum.Enum):
    """Which retriever(s) surfaced a chunk.

    Worth carrying to the UI: "found by keyword only" explains a result whose
    vector distance looks poor, and the mix across a result set is the clearest
    signal that hybrid retrieval is doing something.
    """

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class RetrievedChunk:
    """One candidate passage, with where it came from and how it scored."""

    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    text: str
    source: RetrievalSource
    # Ordering score for the stage that produced this chunk: RRF score after
    # fusion, provider score after reranking. Comparable only within one result
    # set -- never across queries or across stages.
    score: float = 0.0
    # Cosine distance, when a vector retriever saw this chunk. None for
    # keyword-only hits, where reporting a distance would be an invention.
    distance: float | None = None

    def with_score(self, score: float) -> RetrievedChunk:
        return replace(self, score=score)

    def with_text(self, text: str) -> RetrievedChunk:
        return replace(self, text=text)

    @property
    def relevance(self) -> float:
        """Vector relevance on a 0–1 scale, or 0.0 when there is no distance.

        Kept for display continuity with the pre-hybrid API. It says nothing
        about keyword hits, which is exactly why ``score`` and ``source`` exist.
        """
        if self.distance is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.distance))
