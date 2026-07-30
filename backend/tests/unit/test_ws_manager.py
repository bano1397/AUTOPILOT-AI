"""Unit tests for the WebSocket workflow event stream.

The behaviour that matters here is backpressure: these events are published
inside the workflow executor between graph nodes, so a slow browser must never
be able to stall someone else's agent run.
"""

from __future__ import annotations

import asyncio

from app.domain.events import (
    WorkflowCompleted,
    WorkflowStarted,
    WorkflowStepCompleted,
)
from app.platform.events import InProcessEventBus
from app.ws.manager import QUEUE_SIZE, WorkflowEventStream, serialize


def _started(run_id: str = "run-1") -> WorkflowStarted:
    return WorkflowStarted(run_id=run_id, workflow_name="agents.ask", user_id="u1")


class TestSerialize:
    def test_carries_the_type_and_payload(self) -> None:
        message = serialize(_started())

        assert message["type"] == "WorkflowStarted"
        assert message["data"]["run_id"] == "run-1"
        assert message["data"]["workflow_name"] == "agents.ask"
        assert message["occurred_at"]

    def test_drops_the_internal_event_id(self) -> None:
        """Nothing downstream can use it, and it invites false correlation."""
        assert "event_id" not in serialize(_started())["data"]

    def test_is_json_serializable(self) -> None:
        import json

        json.dumps(serialize(WorkflowCompleted(run_id="run-1")))


class TestFanOut:
    def test_a_subscriber_receives_broadcast_events(self) -> None:
        stream = WorkflowEventStream()
        subscriber = stream.register()

        stream.broadcast(_started())

        assert subscriber.queue.get_nowait()["data"]["run_id"] == "run-1"

    def test_every_subscriber_gets_its_own_copy(self) -> None:
        stream = WorkflowEventStream()
        first, second = stream.register(), stream.register()

        stream.broadcast(_started())

        assert first.queue.qsize() == 1
        assert second.queue.qsize() == 1

    def test_a_run_scoped_subscriber_ignores_other_runs(self) -> None:
        stream = WorkflowEventStream()
        subscriber = stream.register(run_id="run-1")

        stream.broadcast(_started("run-2"))
        stream.broadcast(_started("run-1"))

        assert subscriber.queue.qsize() == 1
        assert subscriber.queue.get_nowait()["data"]["run_id"] == "run-1"

    def test_unregistering_stops_delivery(self) -> None:
        stream = WorkflowEventStream()
        subscriber = stream.register()
        stream.unregister(subscriber)

        stream.broadcast(_started())

        assert subscriber.queue.empty()
        assert stream.subscriber_count == 0

    def test_broadcasting_with_no_subscribers_is_harmless(self) -> None:
        WorkflowEventStream().broadcast(_started())


class TestBackpressure:
    def test_a_full_queue_drops_the_oldest_rather_than_blocking(self) -> None:
        """The publisher is the workflow executor; it must never wait."""
        stream = WorkflowEventStream()
        subscriber = stream.register()

        for index in range(QUEUE_SIZE + 10):
            stream.broadcast(
                WorkflowStepCompleted(
                    run_id="run-1", node_name=f"node-{index}", duration_ms=1
                )
            )

        assert subscriber.queue.qsize() == QUEUE_SIZE
        assert subscriber.dropped == 10
        # The newest event survived; the oldest did not.
        names = []
        while not subscriber.queue.empty():
            names.append(subscriber.queue.get_nowait()["data"]["node_name"])
        assert names[-1] == f"node-{QUEUE_SIZE + 9}"
        assert "node-0" not in names

    def test_broadcast_never_awaits(self) -> None:
        """A synchronous call cannot yield to the event loop, which is the
        property that keeps a slow client off the critical path."""
        stream = WorkflowEventStream()
        stream.register()

        assert not asyncio.iscoroutinefunction(stream.broadcast)


class TestEventBusIntegration:
    async def test_subscribes_to_every_workflow_lifecycle_event(self) -> None:
        bus = InProcessEventBus()
        stream = WorkflowEventStream()
        stream.subscribe_to(bus)
        subscriber = stream.register()

        await bus.publish(_started())
        await bus.publish(
            WorkflowStepCompleted(run_id="run-1", node_name="supervisor", duration_ms=3)
        )
        await bus.publish(WorkflowCompleted(run_id="run-1"))

        types = []
        while not subscriber.queue.empty():
            types.append(subscriber.queue.get_nowait()["type"])
        assert types == ["WorkflowStarted", "WorkflowStepCompleted", "WorkflowCompleted"]

    async def test_unrelated_events_are_not_forwarded(self) -> None:
        from app.domain.events import DocumentIndexed

        bus = InProcessEventBus()
        stream = WorkflowEventStream()
        stream.subscribe_to(bus)
        subscriber = stream.register()

        await bus.publish(DocumentIndexed(document_id="d1", chunk_count=3))

        assert subscriber.queue.empty()
