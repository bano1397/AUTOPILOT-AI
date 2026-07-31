"""Prompts for the calendar agent."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.domain.interfaces.calendar import CalendarEvent, FreeSlot
from app.domain.interfaces.llm import ChatMessage, ChatRole, history_to_messages
from app.platform.prompts.catalog import CALENDAR_SYSTEM_PROMPT

CALENDAR_PROMPT_KEY = "agent.calendar.system"
CALENDAR_PROMPT_VERSION = 1

# Enough to answer "what's on this week?" without burning context on a month
# of meetings the question never touches.
_MAX_EVENTS = 20
_MAX_SLOTS = 10


def _stamp(value: datetime) -> str:
    return value.strftime("%a %d %b %H:%M UTC")


def format_schedule(
    events: Sequence[CalendarEvent],
    slots: Sequence[FreeSlot],
    *,
    now: datetime,
) -> str:
    """Render the calendar as the plain text the model is grounded in.

    Written out rather than passed as JSON: the model reads it, and a dumped
    object wastes tokens on syntax while reading worse. "Now" is stated
    explicitly because a model has no clock and would otherwise guess at what
    "tomorrow" means.
    """
    lines = [f"Current time: {_stamp(now)}", ""]

    if events:
        lines.append("Scheduled events:")
        for event in events[:_MAX_EVENTS]:
            attendees = (
                f" with {', '.join(event.attendees)}" if event.attendees else ""
            )
            location = f" at {event.location}" if event.location else ""
            lines.append(
                f"- {_stamp(event.starts_at)}–{event.ends_at.strftime('%H:%M')}: "
                f"{event.title}{attendees}{location}"
            )
        if len(events) > _MAX_EVENTS:
            lines.append(f"- (+{len(events) - _MAX_EVENTS} more)")
    else:
        lines.append("Scheduled events: none in this period.")

    lines.append("")
    if slots:
        lines.append("Free slots (within working hours):")
        for slot in slots[:_MAX_SLOTS]:
            lines.append(
                f"- {_stamp(slot.starts_at)}–{slot.ends_at.strftime('%H:%M')}"
            )
        if len(slots) > _MAX_SLOTS:
            lines.append(f"- (+{len(slots) - _MAX_SLOTS} more)")
    else:
        lines.append("Free slots: none in working hours in this period.")

    return "\n".join(lines)


def build_calendar_messages(
    request: str,
    schedule: str,
    history: Sequence[dict[str, str]] = (),
) -> list[ChatMessage]:
    """Build the grounded scheduling prompt."""
    return [
        ChatMessage(
            role=ChatRole.SYSTEM,
            content=CALENDAR_SYSTEM_PROMPT.render(schedule=schedule),
        ),
        *history_to_messages(history),
        ChatMessage(role=ChatRole.USER, content=request),
    ]
