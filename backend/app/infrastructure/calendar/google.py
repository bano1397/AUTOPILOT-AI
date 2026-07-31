"""Google Calendar adapter — **a seam, not a working integration.**

The blueprint calls for "local default, Google adapter". This is the adapter's
shape: the wire format, the field mapping, and the OAuth requirement, written
down where the next person will look for them. What it is *not* is a Google
integration you can turn on — there is no OAuth flow, no token store, and no
refresh handling, and none of this has been run against Google.

It is here rather than absent because the mapping is the part that is easy to
get wrong and easy to record now: Google returns ``dateTime`` for timed events
and ``date`` for all-day ones, ids are opaque strings rather than UUIDs, and
attendees are objects rather than plain addresses. Every method raises
:class:`CalendarError` naming what is missing, so selecting this provider fails
immediately and loudly instead of silently returning an empty calendar — which
would look like "you have no meetings".

To finish it you need: an OAuth 2.0 client, a per-workspace token store with
refresh, and `https://www.googleapis.com/auth/calendar.events` scope. Then
replace each `_unavailable()` with the corresponding REST call; the parsing
helpers below are already written and unit-tested.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.interfaces.calendar import CalendarError, CalendarEvent, FreeSlot
from app.platform.registry import register_provider

_NOT_IMPLEMENTED = (
    "The Google Calendar adapter is a seam, not a working integration: it has "
    "no OAuth flow or token store. Use CALENDAR_PROVIDER=local, or finish the "
    "adapter (see app/infrastructure/calendar/google.py)."
)


def parse_google_datetime(payload: dict[str, Any]) -> datetime:
    """Read one end of a Google event's time range.

    Google uses ``dateTime`` (RFC 3339, timed) or ``date`` (all-day). All-day
    events are anchored to UTC midnight — an approximation, and the reason a
    real integration must carry the event's ``timeZone`` rather than assume.
    """
    if "dateTime" in payload:
        raw = str(payload["dateTime"]).replace("Z", "+00:00")
        return datetime.fromisoformat(raw).astimezone(UTC)
    if "date" in payload:
        return datetime.fromisoformat(f"{payload['date']}T00:00:00+00:00")
    raise CalendarError(f"Google event time has neither dateTime nor date: {payload!r}")


def parse_google_event(payload: dict[str, Any]) -> CalendarEvent:
    """Map one Google event resource onto the port's shape."""
    try:
        starts_at = parse_google_datetime(payload["start"])
        ends_at = parse_google_datetime(payload["end"])
    except KeyError as exc:
        raise CalendarError(f"Google event is missing {exc}") from exc

    attendees = tuple(
        str(person["email"])
        for person in payload.get("attendees", [])
        if isinstance(person, dict) and person.get("email")
    )
    return CalendarEvent(
        id=str(payload.get("id", "")),
        title=str(payload.get("summary", "(no title)")),
        starts_at=starts_at,
        ends_at=ends_at,
        description=str(payload.get("description", "")),
        location=str(payload.get("location", "")),
        attendees=attendees,
        metadata={"htmlLink": payload.get("htmlLink", "")},
    )


@register_provider(kind="calendar", name="google")
class GoogleCalendarProvider:
    """Placeholder that fails loudly rather than pretending to be empty."""

    name = "google"

    def __init__(self, calendar_id: str = "primary") -> None:
        self._calendar_id = calendar_id

    @staticmethod
    def _unavailable() -> CalendarError:
        return CalendarError(_NOT_IMPLEMENTED)

    async def list_events(
        self, *, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        raise self._unavailable()

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
        raise self._unavailable()

    async def delete_event(self, event_id: str) -> None:
        raise self._unavailable()

    async def free_slots(
        self,
        *,
        start: datetime,
        end: datetime,
        duration: timedelta,
        working_hours: tuple[int, int] = (9, 17),
    ) -> list[FreeSlot]:
        raise self._unavailable()
