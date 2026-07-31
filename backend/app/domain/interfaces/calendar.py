"""Calendar interface (port).

Reads and writes calendar events, and finds gaps between them (blueprint §5,
provider #10). The default implementation stores events in this platform's own
database so scheduling works with no external account; a Google adapter slots
in behind the same contract.

Times are timezone-aware UTC throughout. A naive datetime is rejected rather
than assumed local: "3pm" means different instants to a caller in Karachi and a
calendar in UTC, and silently guessing is how double-bookings happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol


class CalendarError(Exception):
    """Raised when a calendar backend cannot satisfy a request."""


@dataclass(frozen=True)
class CalendarEvent:
    """One scheduled event."""

    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    description: str = ""
    location: str = ""
    attendees: tuple[str, ...] = ()
    # Backend-specific extras (Google's htmlLink, recurrence rules, ...).
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at

    def overlaps(self, start: datetime, end: datetime) -> bool:
        """Whether this event intersects ``[start, end)``.

        Half-open: an event ending exactly when another starts does not
        overlap, so back-to-back meetings are not reported as a conflict.
        """
        return self.starts_at < end and start < self.ends_at


@dataclass(frozen=True)
class FreeSlot:
    """A gap with no events in it."""

    starts_at: datetime
    ends_at: datetime

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


class CalendarProvider(Protocol):
    """Contract for calendar backends."""

    async def list_events(
        self, *, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        """Events overlapping ``[start, end)``, earliest first."""
        ...

    async def create_event(
        self,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        description: str = "",
        location: str = "",
        attendees: tuple[str, ...] = (),
    ) -> CalendarEvent:
        """Create an event and return it with its assigned id."""
        ...

    async def delete_event(self, event_id: str) -> None:
        """Remove an event. Missing ids are not an error (idempotent)."""
        ...

    async def free_slots(
        self,
        *,
        start: datetime,
        end: datetime,
        duration: timedelta,
        working_hours: tuple[int, int] = (9, 17),
    ) -> list[FreeSlot]:
        """Gaps of at least ``duration`` within working hours.

        ``working_hours`` is a half-open (start_hour, end_hour) pair in UTC.
        Without it every overnight gap qualifies, and "when am I free?" answers
        03:00.
        """
        ...
