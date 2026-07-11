"""Response schemas for the notifications feature."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    """One in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime


class UnreadCountRead(BaseModel):
    """Number of unread notifications."""

    count: int


class MarkAllReadRead(BaseModel):
    """How many notifications were marked read."""

    updated: int
