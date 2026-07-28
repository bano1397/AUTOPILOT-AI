"""Request/response schemas for the long-term memory feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.features.memory.models import MemoryKind
from app.features.memory.service import Recollection


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: MemoryKind = MemoryKind.FACT
    source: str | None = Field(default=None, max_length=100)
    meta: dict[str, Any] | None = None


class MemoryRecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    # Omitted means "use the workspace default retrieval breadth".
    top_k: int | None = Field(default=None, ge=1, le=50)


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    kind: MemoryKind
    source: str | None
    meta: dict[str, Any] | None
    vector_id: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def indexed(self) -> bool:
        """Whether this entry is semantically recallable.

        False when embedding failed at write time: the fact is stored and
        listable, but ``recall`` cannot surface it. Exposed rather than hidden
        so the caller is never misled about what was actually indexed.
        """
        return self.vector_id is not None


class RecollectionRead(BaseModel):
    """A recalled memory with its similarity score."""

    entry: MemoryRead
    relevance: float

    @classmethod
    def from_recollection(cls, recollection: Recollection) -> RecollectionRead:
        return cls(
            entry=MemoryRead.model_validate(recollection.entry),
            relevance=round(recollection.relevance, 4),
        )
