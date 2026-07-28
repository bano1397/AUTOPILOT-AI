"""Long-term memory ORM model.

Level 3 of the six-level memory architecture (blueprint §16): durable facts and
past outcomes, as opposed to per-thread conversation history (level 2) or
document chunks (level 4).

The row is the source of truth; the vector is a derived index. ``vector_id``
is nullable so a row can exist before its embedding is written, mirroring how
``DocumentChunk`` is persisted ahead of its upsert — a failed embed leaves a
recallable-by-listing row rather than losing the fact entirely.
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class MemoryKind(str, enum.Enum):
    """What sort of durable fact this is.

    Kinds are advisory: they drive filtering and UI grouping, not behavior.
    """

    FACT = "fact"
    PREFERENCE = "preference"
    OUTCOME = "outcome"


class MemoryEntry(UUIDMixin, TimestampMixin, Base):
    """One durable fact, semantically recallable."""

    __tablename__ = "memory_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(20), default=MemoryKind.FACT.value, nullable=False
    )
    # Free-form provenance: which agent, conversation, or import wrote this.
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Set once the embedding lands in the memory vector namespace.
    vector_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
