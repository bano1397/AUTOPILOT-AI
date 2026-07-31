"""Request/response schemas for the calendar feature."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.interfaces.calendar import CalendarEvent, FreeSlot


class CalendarEventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime
    description: str = Field(default="", max_length=4000)
    location: str = Field(default="", max_length=300)
    attendees: list[str] = Field(default_factory=list)


class CalendarEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    description: str
    location: str
    attendees: list[str]

    @classmethod
    def from_event(cls, event: CalendarEvent) -> CalendarEventRead:
        return cls(
            id=event.id,
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            description=event.description,
            location=event.location,
            attendees=list(event.attendees),
        )


class FreeSlotRead(BaseModel):
    starts_at: datetime
    ends_at: datetime
    minutes: int

    @classmethod
    def from_slot(cls, slot: FreeSlot) -> FreeSlotRead:
        return cls(
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            minutes=int(slot.duration.total_seconds() // 60),
        )
