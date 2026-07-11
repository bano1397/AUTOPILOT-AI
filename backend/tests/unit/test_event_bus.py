"""Tests for the in-process event bus."""

from __future__ import annotations

from app.domain.events import DocumentIndexed, DomainEvent, WorkflowStarted
from app.platform.events import InProcessEventBus


def _started() -> WorkflowStarted:
    return WorkflowStarted(run_id="r1", workflow_name="wf", user_id="u1")


async def test_publish_invokes_matching_handler() -> None:
    bus = InProcessEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(WorkflowStarted, handler)
    event = _started()
    await bus.publish(event)

    assert received == [event]


async def test_publish_skips_non_matching_handler() -> None:
    bus = InProcessEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(WorkflowStarted, handler)
    await bus.publish(DocumentIndexed(document_id="d1", chunk_count=3))

    assert received == []


async def test_base_subscription_receives_subtypes() -> None:
    bus = InProcessEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    # Subscribing to the base type observes every event.
    bus.subscribe(DomainEvent, handler)
    await bus.publish(_started())

    assert len(received) == 1


async def test_handler_failure_is_isolated() -> None:
    bus = InProcessEventBus()
    succeeded: list[DomainEvent] = []

    async def failing(event: DomainEvent) -> None:
        raise RuntimeError("boom")

    async def working(event: DomainEvent) -> None:
        succeeded.append(event)

    bus.subscribe(WorkflowStarted, failing)
    bus.subscribe(WorkflowStarted, working)
    await bus.publish(_started())  # must not raise

    assert len(succeeded) == 1


def test_event_name_is_class_name() -> None:
    assert _started().name == "WorkflowStarted"
