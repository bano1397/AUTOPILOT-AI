"""Email ORM model.

One row per ingested message. The row is the audit trail of what the agent
decided and what a human did about it: classification, extracted entities, the
drafted reply, and the send decision all live here.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin

# Portable JSON: JSONB on Postgres, JSON on SQLite.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class EmailIntent(str, enum.Enum):
    """The nine intents the classifier chooses between (blueprint FR)."""

    QUESTION = "question"
    REQUEST = "request"
    COMPLAINT = "complaint"
    MEETING = "meeting"
    INVOICE = "invoice"
    SALES = "sales"
    SUPPORT = "support"
    SPAM = "spam"
    OTHER = "other"


class EmailStatus(str, enum.Enum):
    """Lifecycle of one message through the agent and its human reviewer."""

    RECEIVED = "received"
    PROCESSING = "processing"
    # A draft exists and is waiting for a human to send or discard it. Nothing
    # leaves the building without that explicit decision.
    AWAITING_APPROVAL = "awaiting_approval"
    SENT = "sent"
    DISCARDED = "discarded"
    FAILED = "failed"


class Email(UUIDMixin, TimestampMixin, Base):
    """An ingested message, its classification, and its drafted reply."""

    __tablename__ = "emails"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Provider identifiers. `message_id` is unique so a re-sync cannot duplicate
    # a message; `uid` is what the provider needs to flag it seen.
    uid: Mapped[str] = mapped_column(String(100), nullable=False)
    message_id: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )

    sender: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    intent: Mapped[EmailIntent | None] = mapped_column(
        Enum(EmailIntent, name="email_intent", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    entities: Mapped[dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)

    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status", values_callable=lambda e: [m.value for m in e]),
        default=EmailStatus.RECEIVED,
        index=True,
        nullable=False,
    )
    draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether the draft was grounded in retrieved documents.
    grounded: Mapped[bool | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
