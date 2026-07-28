"""Request/response schemas for the emails feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.emails.models import EmailIntent, EmailStatus


class EmailRead(BaseModel):
    """One ingested message with its triage result."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sender: str
    subject: str
    body: str
    received_at: datetime | None
    intent: EmailIntent | None
    entities: dict[str, Any]
    status: EmailStatus
    draft: str | None
    grounded: bool | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class SyncResponse(BaseModel):
    """Result of a mailbox sync."""

    fetched: int
    triaged: int
    skipped: int
    failed: int


class SendRequest(BaseModel):
    """Optional final edit of the draft before it goes out."""

    body: str | None = Field(default=None, min_length=1, max_length=20000)
