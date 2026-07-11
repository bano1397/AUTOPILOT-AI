"""Request/response schemas for the RAG feature."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.interfaces.vector_store import VectorMatch


class RagQueryRequest(BaseModel):
    """A semantic search over the caller's indexed documents."""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagAskRequest(BaseModel):
    """A grounded question over the caller's indexed documents."""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagMatchRead(BaseModel):
    """One retrieved chunk with its citation."""

    document_id: str
    filename: str
    chunk_index: int
    text: str
    distance: float

    @classmethod
    def from_vector_match(cls, match: VectorMatch) -> RagMatchRead:
        return cls(
            document_id=str(match.metadata.get("document_id", "")),
            filename=str(match.metadata.get("filename", "")),
            chunk_index=int(match.metadata.get("chunk_index", 0)),
            text=match.text,
            distance=match.distance,
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
