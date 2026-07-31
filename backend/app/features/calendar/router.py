"""Calendar HTTP endpoints (workspace-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status

from app.core.exceptions import ValidationAppError
from app.core.schemas import ApiResponse, MessageResponse
from app.domain.interfaces.calendar import CalendarError, CalendarProvider
from app.features.calendar.dependencies import get_calendar_provider
from app.features.calendar.schemas import (
    CalendarEventCreateRequest,
    CalendarEventRead,
    FreeSlotRead,
)

router = APIRouter()

# A window has to default to something; a fortnight answers "what's coming up?"
DEFAULT_WINDOW_DAYS = 14


def _window(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    resolved_start = start or datetime.now(UTC)
    resolved_end = end or resolved_start + timedelta(days=DEFAULT_WINDOW_DAYS)
    return resolved_start, resolved_end


@router.get("/events", response_model=ApiResponse[list[CalendarEventRead]])
async def list_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    calendar: CalendarProvider = Depends(get_calendar_provider),
) -> ApiResponse[list[CalendarEventRead]]:
    """Events overlapping the window (defaults to the next fortnight)."""
    resolved_start, resolved_end = _window(start, end)
    try:
        events = await calendar.list_events(start=resolved_start, end=resolved_end)
    except CalendarError as exc:
        raise ValidationAppError(str(exc)) from exc
    return ApiResponse(data=[CalendarEventRead.from_event(e) for e in events])


@router.post(
    "/events",
    response_model=ApiResponse[CalendarEventRead],
    status_code=http_status.HTTP_201_CREATED,
)
async def create_event(
    payload: CalendarEventCreateRequest,
    calendar: CalendarProvider = Depends(get_calendar_provider),
) -> ApiResponse[CalendarEventRead]:
    try:
        event = await calendar.create_event(
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            description=payload.description,
            location=payload.location,
            attendees=tuple(payload.attendees),
        )
    except CalendarError as exc:
        raise ValidationAppError(str(exc)) from exc
    return ApiResponse(data=CalendarEventRead.from_event(event))


@router.delete("/events/{event_id}", response_model=ApiResponse[MessageResponse])
async def delete_event(
    event_id: str,
    calendar: CalendarProvider = Depends(get_calendar_provider),
) -> ApiResponse[MessageResponse]:
    """Delete an event. Idempotent: an unknown id is not an error."""
    try:
        await calendar.delete_event(event_id)
    except CalendarError as exc:
        raise ValidationAppError(str(exc)) from exc
    return ApiResponse(data=MessageResponse(message="Event deleted"))


@router.get("/free-slots", response_model=ApiResponse[list[FreeSlotRead]])
async def free_slots(
    minutes: int = Query(default=30, ge=5, le=480),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    open_hour: int = Query(default=9, ge=0, le=23),
    close_hour: int = Query(default=17, ge=1, le=24),
    calendar: CalendarProvider = Depends(get_calendar_provider),
) -> ApiResponse[list[FreeSlotRead]]:
    """Gaps of at least ``minutes`` inside working hours (UTC)."""
    resolved_start, resolved_end = _window(start, end)
    try:
        slots = await calendar.free_slots(
            start=resolved_start,
            end=resolved_end,
            duration=timedelta(minutes=minutes),
            working_hours=(open_hour, close_hour),
        )
    except CalendarError as exc:
        raise ValidationAppError(str(exc)) from exc
    return ApiResponse(data=[FreeSlotRead.from_slot(slot) for slot in slots])
