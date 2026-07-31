"""Calendar event ORM model (the local calendar backend's storage)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class CalendarEventRow(UUIDMixin, TimestampMixin, Base):
    """One event on the local calendar.

    Named ``...Row`` to keep it distinct from the port's
    :class:`~app.domain.interfaces.calendar.CalendarEvent`, which is the shape
    every backend speaks. Only this adapter has rows; the Google adapter has
    none, and nothing outside the adapter should touch this table.
    """

    __tablename__ = "calendar_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Indexed because every read is a range scan over the start time.
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    # A list of email addresses. JSON rather than a join table: attendees are
    # read and written whole, never queried across.
    attendees: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Where this event came from ("local", or a Google event id once synced).
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
