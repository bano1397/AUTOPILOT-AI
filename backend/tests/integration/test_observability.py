"""Integration tests for the AI execution recorder."""

from __future__ import annotations

import json

import pytest
from app.core.logging import correlation_id_var
from app.domain.events import CostRecorded, DomainEvent
from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.platform.events import InProcessEventBus
from app.platform.observability import AiExecution, AiExecutionRecorder
from sqlalchemy import select

from tests.fakes import FakeLLMProvider

_MESSAGES = [
    ChatMessage(role=ChatRole.SYSTEM, content="You are helpful."),
    ChatMessage(role=ChatRole.USER, content="Hello?"),
]


async def _executions(db: SqlAlchemyDatabaseProvider) -> list[AiExecution]:
    async with db.session() as session:
        result = await session.execute(select(AiExecution))
        return list(result.scalars().all())


async def test_successful_call_is_recorded(db: SqlAlchemyDatabaseProvider) -> None:
    bus = InProcessEventBus()
    recorder = AiExecutionRecorder(db=db, bus=bus)
    llm = FakeLLMProvider(reply="hi there")

    result = await recorder.chat(llm, _MESSAGES, feature="rag.ask")

    assert result.content == "hi there"
    rows = await _executions(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.feature == "rag.ask"
    assert row.provider == "fake"
    assert row.model == "fake-llm"
    assert row.prompt_tokens == 7
    assert row.completion_tokens == 3
    assert row.duration_ms == 5
    assert row.response_preview == "hi there"
    assert row.error is None
    prompt = json.loads(row.prompt)
    assert prompt[0] == {"role": "system", "content": "You are helpful."}


async def test_failed_call_is_recorded_and_reraises(
    db: SqlAlchemyDatabaseProvider,
) -> None:
    bus = InProcessEventBus()
    recorder = AiExecutionRecorder(db=db, bus=bus)
    llm = FakeLLMProvider(fail=True)

    with pytest.raises(RuntimeError, match="llm service unavailable"):
        await recorder.chat(llm, _MESSAGES, feature="rag.ask")

    rows = await _executions(db)
    assert len(rows) == 1
    assert rows[0].error == "llm service unavailable"
    assert rows[0].response_preview is None
    assert rows[0].prompt_tokens == 0


async def test_cost_recorded_event_is_published(
    db: SqlAlchemyDatabaseProvider,
) -> None:
    bus = InProcessEventBus()
    received: list[CostRecorded] = []

    async def handler(event: DomainEvent) -> None:
        assert isinstance(event, CostRecorded)
        received.append(event)

    bus.subscribe(CostRecorded, handler)
    recorder = AiExecutionRecorder(db=db, bus=bus)

    await recorder.chat(FakeLLMProvider(), _MESSAGES, feature="rag.ask")

    assert len(received) == 1
    assert received[0].provider == "fake"
    assert received[0].model == "fake-llm"
    assert received[0].cost_usd == 0.0
    rows = await _executions(db)
    assert received[0].execution_id == str(rows[0].id)


async def test_correlation_id_is_captured(db: SqlAlchemyDatabaseProvider) -> None:
    bus = InProcessEventBus()
    recorder = AiExecutionRecorder(db=db, bus=bus)
    token = correlation_id_var.set("cid-observability-test")
    try:
        await recorder.chat(FakeLLMProvider(), _MESSAGES, feature="rag.ask")
    finally:
        correlation_id_var.reset(token)

    rows = await _executions(db)
    assert rows[0].correlation_id == "cid-observability-test"


class _BrokenDb:
    """A database provider whose sessions always fail."""

    def session(self) -> None:
        raise RuntimeError("observability db down")


async def test_recording_failure_does_not_break_the_call() -> None:
    bus = InProcessEventBus()
    recorder = AiExecutionRecorder(db=_BrokenDb(), bus=bus)  # type: ignore[arg-type]
    llm = FakeLLMProvider(reply="still works")

    # Even with the observability store down, the LLM result must come back.
    result = await recorder.chat(llm, _MESSAGES, feature="rag.ask")

    assert result.content == "still works"
