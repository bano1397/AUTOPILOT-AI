"""Conversation and message ORM models.

``Message.position`` provides stable intra-conversation ordering: SQLite
timestamps have second granularity, so the two messages written by a single
exchange would otherwise tie.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class Conversation(UUIDMixin, TimestampMixin, Base):
    """A chat thread owned by a user."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class Message(UUIDMixin, TimestampMixin, Base):
    """One turn within a conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Assistant metadata: agent, model, grounded, sources (for re-rendering).
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
