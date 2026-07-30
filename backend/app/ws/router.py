"""WebSocket endpoint streaming live workflow run status.

Unversioned, like the other system-adjacent surfaces: ``/ws/runs``. Pass
``?run_id=<uuid>`` to follow one run instead of all of them.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import cast

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.ws.manager import Subscriber, WorkflowEventStream

logger = get_logger("app.ws")

router = APIRouter()

# How long to wait for an event before sending a keepalive. Proxies and load
# balancers close idle WebSockets, and an agent run can easily be quiet for
# longer than that while an LLM call is in flight.
KEEPALIVE_SECONDS = 25.0


@router.websocket("/ws/runs")
async def workflow_runs(
    websocket: WebSocket,
    run_id: str | None = Query(default=None),
) -> None:
    """Stream workflow lifecycle events until the client disconnects."""
    stream = cast(WorkflowEventStream, websocket.app.state.event_stream)
    await websocket.accept()
    subscriber = stream.register(run_id)

    try:
        await _pump(websocket, subscriber)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - one bad socket must not surface as a 500
        logger.warning("ws.stream_failed", extra={"run_id": run_id})
    finally:
        stream.unregister(subscriber)
        with contextlib.suppress(Exception):
            await websocket.close()


async def _pump(websocket: WebSocket, subscriber: Subscriber) -> None:
    """Forward queued events, with keepalives during quiet periods."""
    while True:
        try:
            message = await asyncio.wait_for(
                subscriber.queue.get(), timeout=KEEPALIVE_SECONDS
            )
        except TimeoutError:
            await websocket.send_json({"type": "ping"})
            continue

        # Report drops rather than hiding them: a client that missed steps
        # should know its view of the run is incomplete.
        if subscriber.dropped:
            message = {**message, "dropped": subscriber.dropped}
            subscriber.dropped = 0
        await websocket.send_json(message)
