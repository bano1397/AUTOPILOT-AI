"""Redis-backed event bus for multi-replica correctness (Phase 4, F5).

The in-process bus is correct for exactly one replica. Scale to two and each
only sees its own events: a document indexed on A never notifies a client
watching B, and a workflow running on A is invisible to B's live-status
sockets. This bridges them over Redis pub/sub.

**Local delivery stays synchronous and comes first.** That is not an
optimisation, it is a correctness requirement: document ingestion is driven by
awaiting ``publish(DocumentUploaded)``, so an upload must not return until its
handler has run. Routing local events through Redis and back would make that
fire-and-forget and break the upload contract. So handlers run locally, then
the event is mirrored to other replicas.

The consequence is the honest one: if Redis is down, the platform degrades
precisely to in-process behaviour — everything still works on the replica that
received the request, and other replicas simply do not hear about it. A
publish failure is logged, never raised, because losing a cross-replica
notification must not fail the user's request that triggered it.

Delivery is at-most-once and unordered across replicas, which is what Redis
pub/sub offers. Every consumer here is a notification or a status update, so
that is acceptable; anything needing guaranteed delivery belongs in a real
queue, not on this bus.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from typing import Any

from app.core.logging import get_logger
from app.domain.events import DomainEvent
from app.domain.interfaces.event_bus import EventHandler
from app.platform.events.bus import InProcessEventBus

logger = get_logger("app.events.redis")

CHANNEL = "autopilot:events"

# Every event class that can cross a replica boundary, by name. An allow-list,
# not a dynamic lookup: a payload arriving over the wire must never be able to
# name an arbitrary importable class.
_EVENT_TYPES: dict[str, type[DomainEvent]] = {}


def _event_catalogue() -> dict[str, type[DomainEvent]]:
    global _EVENT_TYPES
    if not _EVENT_TYPES:
        from app.domain import events as catalogue

        _EVENT_TYPES = {
            name: value
            for name, value in vars(catalogue).items()
            if isinstance(value, type)
            and issubclass(value, DomainEvent)
            and value is not DomainEvent
        }
    return _EVENT_TYPES


class RedisEventBus:
    """In-process delivery, mirrored to other replicas over Redis pub/sub."""

    def __init__(self, url: str, *, client: Any | None = None) -> None:
        self._url = url
        self._client = client
        self._local = InProcessEventBus()
        # Distinguishes our own mirrored events from other replicas', so a
        # publisher does not handle its own event twice.
        self._origin = str(uuid.uuid4())
        self._task: asyncio.Task[None] | None = None
        self._pubsub: Any = None

    # -- EventBus contract ---------------------------------------------------

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._local.subscribe(event_type, handler)

    async def publish(self, event: DomainEvent) -> None:
        """Deliver locally, then mirror to the other replicas."""
        await self._local.publish(event)
        await self._mirror(event)

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Connect and begin consuming events published by other replicas."""
        if self._task is not None:
            return
        try:
            client = await self._connect()
            self._pubsub = client.pubsub()
            await self._pubsub.subscribe(CHANNEL)
        except Exception as exc:  # noqa: BLE001 - degradation is deliberate
            logger.warning(
                "redis_bus.subscribe_failed",
                extra={"error": str(exc), "effect": "running single-replica"},
            )
            return
        self._task = asyncio.create_task(self._consume())
        logger.info("redis_bus.started", extra={"channel": CHANNEL})

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(CHANNEL)
                await self._pubsub.aclose()
            self._pubsub = None

    # -- internals -----------------------------------------------------------

    async def _connect(self) -> Any:
        if self._client is None:
            import redis.asyncio as redis

            # Through an Any-typed local: redis-py ships no annotation for
            # from_url, so a direct call fails mypy *only when the optional
            # extra is installed* -- which would make the type gate pass in CI
            # and fail on a developer's machine.
            factory: Any = redis.from_url
            self._client = factory(self._url, decode_responses=True)
        return self._client

    async def _mirror(self, event: DomainEvent) -> None:
        payload = json.dumps(
            {
                "origin": self._origin,
                "type": event.name,
                "data": event.model_dump(mode="json"),
            }
        )
        try:
            client = await self._connect()
            await client.publish(CHANNEL, payload)
        except Exception as exc:  # noqa: BLE001 - never fail the caller
            logger.warning(
                "redis_bus.publish_failed",
                extra={"event": event.name, "error": str(exc)},
            )

    async def _consume(self) -> None:
        """Dispatch events other replicas published. Runs until cancelled."""
        assert self._pubsub is not None  # noqa: S101 - start() guarantees it
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a dropped connection
                logger.warning("redis_bus.receive_failed", extra={"error": str(exc)})
                await asyncio.sleep(1.0)
                continue

            if message is None:
                continue
            event = self._decode(message.get("data"))
            if event is not None:
                # Local handlers only: re-mirroring would loop forever.
                await self._local.publish(event)

    def _decode(self, raw: Any) -> DomainEvent | None:
        if not isinstance(raw, str):
            return None
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("redis_bus.undecodable_message")
            return None

        if envelope.get("origin") == self._origin:
            # Our own event, already delivered locally before publishing.
            return None

        event_type = _event_catalogue().get(str(envelope.get("type", "")))
        if event_type is None:
            # An event this replica's version does not know about — likely a
            # rolling deploy. Ignoring it is correct; guessing would not be.
            logger.info(
                "redis_bus.unknown_event", extra={"type": envelope.get("type")}
            )
            return None

        try:
            return event_type.model_validate(envelope.get("data") or {})
        except Exception as exc:  # noqa: BLE001 - a malformed remote payload
            logger.warning(
                "redis_bus.invalid_payload",
                extra={"type": envelope.get("type"), "error": str(exc)},
            )
            return None
