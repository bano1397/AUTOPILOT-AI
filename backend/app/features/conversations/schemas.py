"""Response schemas for the conversations feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConversationRead(BaseModel):
    """A conversation summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    """One message in a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    role: str
    content: str
    meta: dict[str, Any] | None
    created_at: datetime


class ConversationDetailRead(BaseModel):
    """A conversation with its full message history."""

    conversation: ConversationRead
    messages: list[MessageRead]
