"""In-process event bus implementation.

Handlers are dispatched by ``isinstance`` check, so subscribing to a base event
type (e.g. :class:`~app.domain.events.DomainEvent`) receives all of its subtypes.
Handler exceptions are caught and logged so a failing subscriber never breaks the
publisher or other subscribers (at-least-once, best-effort delivery).
"""

from __future__ import annotations

from collections import defaultdict

from app.core.logging import get_logger
from app.domain.events import DomainEvent
from app.domain.interfaces.event_bus import EventHandler

logger = get_logger("app.events")


class InProcessEventBus:
    """A simple asynchronous, single-process publish/subscribe event bus."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("event_subscribed", extra={"event_type": event_type.__name__})

    async def publish(self, event: DomainEvent) -> None:
        dispatched = 0
        for registered_type, handlers in list(self._handlers.items()):
            if isinstance(event, registered_type):
                for handler in handlers:
                    try:
                        await handler(event)
                        dispatched += 1
                    except Exception:  # noqa: BLE001 - handler isolation is intentional
                        logger.exception(
                            "event_handler_failed", extra={"event": event.name}
                        )
        logger.debug(
            "event_published", extra={"event": event.name, "handlers": dispatched}
        )
