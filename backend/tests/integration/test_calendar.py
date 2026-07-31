"""Integration tests for the calendar feature.

The free-slot search carries the real logic here — overlap, merging,
back-to-back meetings, working hours — so most of these exercise it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from app.domain.interfaces.calendar import CalendarError
from app.infrastructure.calendar import GoogleCalendarProvider, LocalCalendarProvider
from app.infrastructure.calendar.google import parse_google_event
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import workspace_user_id

# A fixed Monday, so "working hours" assertions do not drift with the calendar.
MONDAY = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


def at(hour: int, minute: int = 0, *, day: int = 0) -> datetime:
    return MONDAY + timedelta(days=day, hours=hour, minutes=minute)


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def calendar(
    db: SqlAlchemyDatabaseProvider,
) -> AsyncIterator[LocalCalendarProvider]:
    user_id = await workspace_user_id(db)
    async with db.session() as session:
        yield LocalCalendarProvider(session, user_id)


class TestLocalCalendarEvents:
    async def test_create_and_read_back(
        self, calendar: LocalCalendarProvider
    ) -> None:
        created = await calendar.create_event(
            title="Standup",
            starts_at=at(9),
            ends_at=at(9, 30),
            attendees=("sam@example.com",),
        )

        events = await calendar.list_events(start=at(0), end=at(23))

        assert [e.id for e in events] == [created.id]
        assert events[0].title == "Standup"
        assert events[0].attendees == ("sam@example.com",)

    async def test_events_are_ordered_by_start(
        self, calendar: LocalCalendarProvider
    ) -> None:
        await calendar.create_event(title="Late", starts_at=at(15), ends_at=at(16))
        await calendar.create_event(title="Early", starts_at=at(10), ends_at=at(11))

        events = await calendar.list_events(start=at(0), end=at(23))

        assert [e.title for e in events] == ["Early", "Late"]

    async def test_an_event_straddling_the_window_is_included(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """Overlap, not containment: a meeting that started before the window
        and runs into it is very much part of that window."""
        await calendar.create_event(
            title="Long workshop", starts_at=at(8), ends_at=at(17)
        )

        events = await calendar.list_events(start=at(12), end=at(13))

        assert [e.title for e in events] == ["Long workshop"]

    async def test_an_event_outside_the_window_is_excluded(
        self, calendar: LocalCalendarProvider
    ) -> None:
        await calendar.create_event(title="Tomorrow", starts_at=at(9, day=1), ends_at=at(10, day=1))

        assert await calendar.list_events(start=at(0), end=at(23)) == []

    async def test_delete_is_idempotent(
        self, calendar: LocalCalendarProvider
    ) -> None:
        created = await calendar.create_event(
            title="Cancelled", starts_at=at(9), ends_at=at(10)
        )

        await calendar.delete_event(created.id)
        await calendar.delete_event(created.id)
        await calendar.delete_event("not-a-uuid")

        assert await calendar.list_events(start=at(0), end=at(23)) == []


class TestValidation:
    async def test_naive_datetimes_are_rejected(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """"3pm" means different instants in different places; guessing is how
        double-bookings happen."""
        with pytest.raises(CalendarError, match="timezone-aware"):
            await calendar.list_events(
                start=datetime(2026, 6, 1, 9), end=datetime(2026, 6, 1, 17)
            )

    async def test_an_event_must_end_after_it_starts(
        self, calendar: LocalCalendarProvider
    ) -> None:
        with pytest.raises(CalendarError, match="end after"):
            await calendar.create_event(
                title="Backwards", starts_at=at(10), ends_at=at(9)
            )

    async def test_an_event_needs_a_title(
        self, calendar: LocalCalendarProvider
    ) -> None:
        with pytest.raises(CalendarError, match="title"):
            await calendar.create_event(title="   ", starts_at=at(9), ends_at=at(10))

    async def test_the_search_window_is_bounded(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """An unbounded search scans the table to answer nothing useful."""
        with pytest.raises(CalendarError, match="limited to"):
            await calendar.free_slots(
                start=at(0), end=at(0, day=400), duration=timedelta(minutes=30)
            )


class TestFreeSlots:
    async def test_an_empty_day_is_one_slot_of_working_hours(
        self, calendar: LocalCalendarProvider
    ) -> None:
        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=30)
        )

        assert len(slots) == 1
        assert slots[0].starts_at == at(9)
        assert slots[0].ends_at == at(17)

    async def test_a_meeting_splits_the_day_in_two(
        self, calendar: LocalCalendarProvider
    ) -> None:
        await calendar.create_event(title="Review", starts_at=at(12), ends_at=at(13))

        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=30)
        )

        assert [(s.starts_at, s.ends_at) for s in slots] == [
            (at(9), at(12)),
            (at(13), at(17)),
        ]

    async def test_gaps_shorter_than_the_requested_duration_are_dropped(
        self, calendar: LocalCalendarProvider
    ) -> None:
        await calendar.create_event(title="A", starts_at=at(9), ends_at=at(11))
        await calendar.create_event(title="B", starts_at=at(11, 15), ends_at=at(17))

        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=30)
        )

        assert slots == [], "a 15-minute gap cannot hold a 30-minute meeting"

    async def test_back_to_back_meetings_produce_no_phantom_gap(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """Half-open intervals: an event ending as another starts is not a gap
        and not a conflict."""
        await calendar.create_event(title="A", starts_at=at(9), ends_at=at(12))
        await calendar.create_event(title="B", starts_at=at(12), ends_at=at(14))

        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=15)
        )

        assert [(s.starts_at, s.ends_at) for s in slots] == [(at(14), at(17))]

    async def test_overlapping_meetings_are_merged_before_subtracting(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """Double-booked time is busy once, not twice."""
        await calendar.create_event(title="A", starts_at=at(10), ends_at=at(12))
        await calendar.create_event(title="B", starts_at=at(11), ends_at=at(13))

        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=30)
        )

        assert [(s.starts_at, s.ends_at) for s in slots] == [
            (at(9), at(10)),
            (at(13), at(17)),
        ]

    async def test_slots_stay_inside_working_hours(
        self, calendar: LocalCalendarProvider
    ) -> None:
        """Without this, "when am I free?" answers 03:00."""
        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59), duration=timedelta(minutes=30)
        )

        for slot in slots:
            assert slot.starts_at.hour >= 9
            assert slot.ends_at.hour <= 17

    async def test_working_hours_are_configurable(
        self, calendar: LocalCalendarProvider
    ) -> None:
        slots = await calendar.free_slots(
            start=at(0),
            end=at(23, 59),
            duration=timedelta(minutes=30),
            working_hours=(8, 12),
        )

        assert [(s.starts_at, s.ends_at) for s in slots] == [(at(8), at(12))]

    async def test_multiple_days_each_contribute_a_slot(
        self, calendar: LocalCalendarProvider
    ) -> None:
        slots = await calendar.free_slots(
            start=at(0), end=at(23, 59, day=2), duration=timedelta(hours=1)
        )

        assert len(slots) == 3
        assert [s.starts_at.day for s in slots] == [1, 2, 3]


class TestCalendarApi:
    async def test_create_list_and_delete_over_http(self, api: AsyncClient) -> None:
        created = await api.post(
            "/api/v1/calendar/events",
            json={
                "title": "Kickoff",
                "starts_at": at(9).isoformat(),
                "ends_at": at(10).isoformat(),
                "attendees": ["sam@example.com"],
            },
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["data"]["id"]

        listed = await api.get(
            "/api/v1/calendar/events",
            params={"start": at(0).isoformat(), "end": at(23).isoformat()},
        )
        assert [e["title"] for e in listed.json()["data"]] == ["Kickoff"]

        deleted = await api.delete(f"/api/v1/calendar/events/{event_id}")
        assert deleted.status_code == 200

        empty = await api.get(
            "/api/v1/calendar/events",
            params={"start": at(0).isoformat(), "end": at(23).isoformat()},
        )
        assert empty.json()["data"] == []

    async def test_free_slots_over_http(self, api: AsyncClient) -> None:
        await api.post(
            "/api/v1/calendar/events",
            json={
                "title": "Blocked",
                "starts_at": at(9).isoformat(),
                "ends_at": at(15).isoformat(),
            },
        )

        response = await api.get(
            "/api/v1/calendar/free-slots",
            params={
                "minutes": 60,
                "start": at(0).isoformat(),
                "end": at(23).isoformat(),
            },
        )

        slots = response.json()["data"]
        assert len(slots) == 1
        assert slots[0]["minutes"] == 120

    async def test_a_backwards_event_is_rejected_with_422(
        self, api: AsyncClient
    ) -> None:
        response = await api.post(
            "/api/v1/calendar/events",
            json={
                "title": "Backwards",
                "starts_at": at(10).isoformat(),
                "ends_at": at(9).isoformat(),
            },
        )

        assert response.status_code == 422


class TestGoogleSeam:
    """The adapter is a documented seam; these pin that it says so."""

    async def test_every_method_fails_loudly(self) -> None:
        """An empty calendar would read as "you have no meetings", which is a
        far worse failure than an error."""
        provider = GoogleCalendarProvider()

        for call in (
            provider.list_events(start=at(0), end=at(1)),
            provider.delete_event("x"),
            provider.free_slots(
                start=at(0), end=at(1), duration=timedelta(minutes=30)
            ),
        ):
            with pytest.raises(CalendarError, match="seam"):
                await call

    def test_the_event_mapping_is_implemented_and_correct(self) -> None:
        """The mapping is the fiddly part, so it is written and tested now."""
        event = parse_google_event(
            {
                "id": "abc123",
                "summary": "Sync",
                "start": {"dateTime": "2026-06-01T09:00:00Z"},
                "end": {"dateTime": "2026-06-01T09:30:00Z"},
                "attendees": [{"email": "sam@example.com"}, {"optional": True}],
                "location": "Room 2",
            }
        )

        assert event.id == "abc123"
        assert event.title == "Sync"
        assert event.starts_at == at(9)
        assert event.ends_at == at(9, 30)
        assert event.attendees == ("sam@example.com",)
        assert event.location == "Room 2"

    def test_all_day_events_map_to_utc_midnight(self) -> None:
        event = parse_google_event(
            {
                "id": "d1",
                "summary": "Holiday",
                "start": {"date": "2026-06-01"},
                "end": {"date": "2026-06-02"},
            }
        )

        assert event.starts_at == at(0)
        assert event.ends_at == at(0, day=1)

    def test_a_time_with_neither_shape_is_rejected(self) -> None:
        with pytest.raises(CalendarError, match="neither"):
            parse_google_event(
                {"id": "x", "start": {"weird": 1}, "end": {"weird": 2}}
            )


class TestCalendarAgent:
    """The agent must answer from the real calendar, not from the model."""

    async def test_a_scheduling_question_routes_to_the_calendar_agent(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        from app.infrastructure.llm.stub import StubLLMProvider
        from app.platform.observability import AiExecutionRecorder

        app.state.llm = StubLLMProvider()
        app.state.ai_recorder = AiExecutionRecorder(db=app.state.db, bus=app.state.event_bus)

        response = await api.post(
            "/api/v1/agents/ask", json={"message": "what meetings do I have?"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["agent"] == "calendar"

    async def test_the_prompt_carries_the_real_schedule(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Grounding is the whole point: a model with no calendar data will
        invent a meeting, and an invented meeting is worse than no answer."""
        from app.platform.observability import AiExecutionRecorder

        from tests.fakes import FakeLLMProvider

        fake = FakeLLMProvider(replies=["calendar", "You have one meeting."])
        app.state.llm = fake
        app.state.ai_recorder = AiExecutionRecorder(db=app.state.db, bus=app.state.event_bus)

        # An event inside the agent's forward-looking window.
        from datetime import UTC, datetime, timedelta

        soon = datetime.now(UTC) + timedelta(hours=2)
        await api.post(
            "/api/v1/calendar/events",
            json={
                "title": "Budget review",
                "starts_at": soon.isoformat(),
                "ends_at": (soon + timedelta(hours=1)).isoformat(),
            },
        )

        await api.post("/api/v1/agents/ask", json={"message": "what is on today?"})

        # Call 1 = supervisor routing, call 2 = the calendar agent.
        system_message = fake.calls[1][0].content
        assert "Budget review" in system_message
        assert "Current time:" in system_message

    async def test_a_broken_calendar_backend_answers_instead_of_500ing(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Selecting the Google seam must not take the agent down with it."""
        from app.core.config import get_settings
        from app.platform.observability import AiExecutionRecorder

        from tests.fakes import FakeLLMProvider

        app.state.llm = FakeLLMProvider(replies=["calendar", "unused"])
        app.state.ai_recorder = AiExecutionRecorder(db=app.state.db, bus=app.state.event_bus)
        settings = get_settings()
        original = settings.calendar_provider
        object.__setattr__(settings, "calendar_provider", "google")
        try:
            response = await api.post(
                "/api/v1/agents/ask", json={"message": "when am I free?"}
            )
        finally:
            object.__setattr__(settings, "calendar_provider", original)

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["agent"] == "calendar"
        assert "can't read your calendar" in data["answer"]
        assert data["grounded"] is False
