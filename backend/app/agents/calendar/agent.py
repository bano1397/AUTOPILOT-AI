"""Calendar agent: answers scheduling questions from the real calendar.

Grounded the same way the knowledge agent is, and for the same reason. A model
asked "when am I free Thursday?" with no data will confidently invent a time,
and a confidently invented meeting slot is worse than no answer. So the agent
reads the calendar first and the model only ever phrases what it was given.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.calendar.prompts import (
    CALENDAR_PROMPT_KEY,
    CALENDAR_PROMPT_VERSION,
    build_calendar_messages,
    format_schedule,
)
from app.domain.interfaces.calendar import CalendarError, CalendarProvider
from app.domain.interfaces.llm import LLMProvider
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent
from app.workflows.state import AgentState

# How far ahead to read when answering an open-ended scheduling question.
LOOKAHEAD_DAYS = 14
# Default meeting length when proposing slots.
DEFAULT_SLOT = timedelta(minutes=30)


@register_agent(supervisor_routable=True)
class CalendarAgent(BaseAgent):
    """Answers questions about the user's schedule and free time."""

    name: ClassVar[str] = "calendar"
    description: ClassVar[str] = (
        "Answers questions about your schedule, meetings, and when you're free."
    )

    def __init__(
        self,
        calendar: CalendarProvider,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
    ) -> None:
        self._calendar = calendar
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        user_id = state.get("user_id")
        request = state.get("request", "")
        now = datetime.now(UTC)
        window_end = now + timedelta(days=LOOKAHEAD_DAYS)

        try:
            events = await self._calendar.list_events(start=now, end=window_end)
            slots = await self._calendar.free_slots(
                start=now, end=window_end, duration=DEFAULT_SLOT
            )
        except CalendarError as exc:
            # A misconfigured calendar (e.g. the Google seam) must produce a
            # clear answer, not a 500 and not a hallucinated schedule.
            return {
                "agent": self.name,
                "answer": f"I can't read your calendar right now: {exc}",
                "model": None,
                "grounded": False,
                "sources": [],
            }

        schedule = format_schedule(events, slots, now=now)
        result = await self._recorder.chat(
            self._llm,
            build_calendar_messages(request, schedule, state.get("history", [])),
            feature="agent.calendar",
            agent_name=self.name,
            user_id=UUID(user_id) if user_id else None,
            temperature=0.2,
            prompt_key=CALENDAR_PROMPT_KEY,
            prompt_version=CALENDAR_PROMPT_VERSION,
        )
        return {
            "agent": self.name,
            "answer": result.content,
            "model": result.model,
            # Grounded in the calendar, the same claim the knowledge agent
            # makes about documents.
            "grounded": True,
            "sources": [],
        }
