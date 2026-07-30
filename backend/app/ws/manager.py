"""WebSocket fan-out of workflow lifecycle events (blueprint §20).

Runs stream through the event bus already — ``WorkflowStarted``,
``WorkflowStepCompleted``, ``WorkflowCompleted``, ``WorkflowFailed``. This
module forwards them to browsers so a run's progress is visible while it
happens instead of only after the request returns.

**The publisher must never be blocked by a subscriber.** These events are
published *inside* the workflow executor, awaited between graph nodes. If a
handler awaited a slow socket, one browser on a bad connection would stall
someone else's agent run. So each connection owns a bounded queue and the
handler only ever does a non-blocking put: when a client cannot keep up, its
oldest event is dropped and a ``dropped`` counter goes out with the next
message, rather than applying backpressure to the graph.

**Single process only.** The event bus is in-process (see F5 in
``docs/COMPLETION_PLAN.md``), so a client connected to replica A never sees
runs executing on replica B. Correct for the single-replica deployment this
targets; a Redis pub/sub bus is the fix, and it is not built.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.domain.events import (
    DomainEvent,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
    WorkflowStepCompleted,
)
from app.domain.interfaces.event_bus import EventBus

logger = get_logger("app.ws")

# Per-connection buffer. Deep enough to absorb a burst of step events from one
# run, shallow enough that a dead-but-not-yet-closed socket cannot accumulate
# unbounded memory.
QUEUE_SIZE = 100

WORKFLOW_EVENTS: tuple[type[DomainEvent], ...] = (
    WorkflowStarted,
    WorkflowStepCompleted,
    WorkflowCompleted,
    WorkflowFailed,
)


def serialize(event: DomainEvent) -> dict[str, Any]:
    """Render an event as the JSON envelope clients receive."""
    payload = event.model_dump(mode="json")
    payload.pop("event_id", None)
    return {
        "type": event.name,
        "occurred_at": payload.pop("occurred_at", None),
        "data": payload,
    }


# eq=False keeps identity semantics: two connections watching the same run are
# distinct subscribers, and the fan-out set is keyed on the connection itself.
@dataclass(eq=False)
class Subscriber:
    """One connected client and its bounded outbox."""

    # None means "every run"; a run id narrows the stream to that run.
    run_id: str | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE)
    )
    dropped: int = 0

    def wants(self, message: dict[str, Any]) -> bool:
        if self.run_id is None:
            return True
        return str(message.get("data", {}).get("run_id", "")) == self.run_id

    def offer(self, message: dict[str, Any]) -> None:
        """Enqueue without ever awaiting; drop the oldest when full."""
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.dropped += 1
            with contextlib.suppress(asyncio.QueueFull):
                self.queue.put_nowait(message)


class WorkflowEventStream:
    """Fans workflow events out to subscribed WebSocket clients."""

    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def register(self, run_id: str | None = None) -> Subscriber:
        subscriber = Subscriber(run_id=run_id)
        self._subscribers.add(subscriber)
        logger.debug("ws.subscribed", extra={"run_id": run_id})
        return subscriber

    def unregister(self, subscriber: Subscriber) -> None:
        self._subscribers.discard(subscriber)
        logger.debug("ws.unsubscribed", extra={"dropped": subscriber.dropped})

    def broadcast(self, event: DomainEvent) -> None:
        """Offer an event to every interested subscriber. Never blocks."""
        if not self._subscribers:
            return
        message = serialize(event)
        for subscriber in list(self._subscribers):
            if subscriber.wants(message):
                subscriber.offer(message)

    def subscribe_to(self, bus: EventBus) -> None:
        """Attach to the event bus for every workflow lifecycle event."""

        async def handler(event: DomainEvent) -> None:
            self.broadcast(event)

        for event_type in WORKFLOW_EVENTS:
            bus.subscribe(event_type, handler)


EventStreamFactory = Callable[[], Awaitable[WorkflowEventStream]]
