"""Event bus interface (port).

Defines the contract producers and consumers depend on. The default in-process
implementation lives in ``app.platform.events``; a distributed implementation
(e.g. Redis pub/sub) can be substituted without changing callers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.domain.events import DomainEvent

# A coroutine function that handles a published event.
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    """Publish/subscribe contract for domain events."""

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Register ``handler`` to receive events of ``event_type`` (and subtypes)."""
        ...

    async def publish(self, event: DomainEvent) -> None:
        """Deliver ``event`` to all matching subscribed handlers."""
        ...
