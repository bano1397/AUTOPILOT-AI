"""Request/response schemas for the RAG feature."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.platform.rag.types import RetrievedChunk


class RagQueryRequest(BaseModel):
    """A semantic search over the caller's indexed documents."""

    query: str = Field(min_length=1, max_length=2000)
    # None means "use the workspace's default_top_k preference".
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagAskRequest(BaseModel):
    """A grounded question over the caller's indexed documents."""

    query: str = Field(min_length=1, max_length=2000)
    # None means "use the workspace's default_top_k preference".
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagMatchRead(BaseModel):
    """One retrieved chunk with its citation and how it was found."""

    document_id: str
    filename: str
    chunk_index: int
    text: str
    # Which retriever(s) surfaced this chunk: "vector", "keyword", or "hybrid".
    retrieval: str = "vector"
    # Ordering score within this result set (RRF, or the reranker's score).
    # Not comparable across queries.
    score: float = 0.0
    # Cosine distance, present only when a vector retriever saw this chunk.
    # None for keyword-only hits, where any number would be invented.
    distance: float | None = None

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> RagMatchRead:
        return cls(
            document_id=chunk.document_id,
            filename=chunk.filename,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            retrieval=chunk.source.value,
            score=round(chunk.score, 6),
            distance=chunk.distance,
        )


class RagQueryRead(BaseModel):
    """Result of a RAG query."""

    query: str
    matches: list[RagMatchRead]


class RagAskRead(BaseModel):
    """Result of a grounded ask: the answer plus the sources it drew on."""

    query: str
    answer: str
    grounded: bool
    model: str | None
    sources: list[RagMatchRead]
