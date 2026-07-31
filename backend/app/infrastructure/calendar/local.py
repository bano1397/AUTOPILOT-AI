"""Local calendar backed by this platform's own database.

The default, so scheduling works with no Google account and no paid key. It is
a real implementation, not a placeholder: events persist, ranges query
correctly, and free-slot search handles overlapping and back-to-back meetings.

What it is *not* is a synced calendar — it knows only about events created
here. That is the line the Google adapter crosses, and this docstring is the
honest statement of it.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.calendar import (
    CalendarError,
    CalendarEvent,
    FreeSlot,
)
from app.features.calendar.models import CalendarEventRow
from app.platform.registry import register_provider

# A slot search spanning years would scan the whole table and answer a question
# nobody asked; a fortnight covers "when are we free?" in practice.
MAX_SEARCH_DAYS = 60


def _require_aware(value: datetime, label: str) -> datetime:
    """Reject naive datetimes rather than guessing a timezone."""
    if value.tzinfo is None:
        raise CalendarError(
            f"{label} must be timezone-aware; a naive datetime is ambiguous"
        )
    return value.astimezone(UTC)


def _to_event(row: CalendarEventRow) -> CalendarEvent:
    # SQLite hands back naive datetimes even for timezone-aware columns, so
    # the UTC tag is reattached on the way out. Without this, comparisons
    # against aware datetimes raise at runtime.
    starts = row.starts_at if row.starts_at.tzinfo else row.starts_at.replace(tzinfo=UTC)
    ends = row.ends_at if row.ends_at.tzinfo else row.ends_at.replace(tzinfo=UTC)
    return CalendarEvent(
        id=str(row.id),
        title=row.title,
        starts_at=starts,
        ends_at=ends,
        description=row.description,
        location=row.location,
        attendees=tuple(row.attendees or ()),
        metadata=dict(row.meta or {}),
    )


@register_provider(kind="calendar", name="local")
class LocalCalendarProvider:
    """Calendar events stored in the platform's own database."""

    name = "local"

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def list_events(
        self, *, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        start = _require_aware(start, "start")
        end = _require_aware(end, "end")
        if end <= start:
            raise CalendarError("end must be after start")

        # Overlap, not containment: a meeting that began before the window and
        # runs into it is very much part of that window.
        result = await self._session.execute(
            select(CalendarEventRow)
            .where(
                CalendarEventRow.user_id == self._user_id,
                CalendarEventRow.starts_at < end,
                CalendarEventRow.ends_at > start,
            )
            .order_by(CalendarEventRow.starts_at)
        )
        return [_to_event(row) for row in result.scalars().all()]

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
        starts_at = _require_aware(starts_at, "starts_at")
        ends_at = _require_aware(ends_at, "ends_at")
        if ends_at <= starts_at:
            raise CalendarError("An event must end after it starts")
        if not title.strip():
            raise CalendarError("An event needs a title")

        row = CalendarEventRow(
            user_id=self._user_id,
            title=title.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            description=description,
            location=location,
            attendees=list(attendees),
            external_id=None,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _to_event(row)

    async def delete_event(self, event_id: str) -> None:
        try:
            parsed = UUID(event_id)
        except ValueError:
            # An unparsable id is simply not present; deletion is idempotent.
            return
        await self._session.execute(
            delete(CalendarEventRow).where(
                CalendarEventRow.id == parsed,
                CalendarEventRow.user_id == self._user_id,
            )
        )
        await self._session.commit()

    async def free_slots(
        self,
        *,
        start: datetime,
        end: datetime,
        duration: timedelta,
        working_hours: tuple[int, int] = (9, 17),
    ) -> list[FreeSlot]:
        """Gaps of at least ``duration`` inside working hours.

        Walks each day's working window, subtracting the events that intersect
        it. Events are merged first, so overlapping and back-to-back meetings
        do not produce phantom zero-length gaps between them.
        """
        start = _require_aware(start, "start")
        end = _require_aware(end, "end")
        if end <= start:
            raise CalendarError("end must be after start")
        if duration <= timedelta(0):
            raise CalendarError("duration must be positive")
        if (end - start).days > MAX_SEARCH_DAYS:
            raise CalendarError(
                f"Slot search is limited to {MAX_SEARCH_DAYS} days"
            )

        open_hour, close_hour = working_hours
        if not 0 <= open_hour < close_hour <= 24:
            raise CalendarError("working_hours must be (open, close) with open < close")

        events = await self.list_events(start=start, end=end)
        busy = _merge([(event.starts_at, event.ends_at) for event in events])

        slots: list[FreeSlot] = []
        for window_start, window_end in _working_windows(
            start, end, open_hour, close_hour
        ):
            cursor = window_start
            for busy_start, busy_end in busy:
                if busy_end <= cursor or busy_start >= window_end:
                    continue
                if busy_start - cursor >= duration:
                    slots.append(FreeSlot(starts_at=cursor, ends_at=busy_start))
                cursor = max(cursor, busy_end)
            if window_end - cursor >= duration:
                slots.append(FreeSlot(starts_at=cursor, ends_at=window_end))
        return slots


def _merge(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Collapse overlapping and touching intervals into disjoint ones."""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for current_start, current_end in ordered[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    return merged


def _working_windows(
    start: datetime, end: datetime, open_hour: int, close_hour: int
) -> list[tuple[datetime, datetime]]:
    """The working portion of each day in ``[start, end)``, clipped to it."""
    windows: list[tuple[datetime, datetime]] = []
    day = start.date()
    while day <= end.date():
        open_at = datetime.combine(day, time(hour=open_hour), tzinfo=UTC)
        close_at = (
            datetime.combine(day, time(0), tzinfo=UTC) + timedelta(hours=close_hour)
        )
        window_start = max(open_at, start)
        window_end = min(close_at, end)
        if window_start < window_end:
            windows.append((window_start, window_end))
        day += timedelta(days=1)
    return windows
