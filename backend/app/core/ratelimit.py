"""In-memory sliding-window rate limiting.

App-scoped (one limiter per application instance) so tests stay isolated. The
window state lives in process memory; a Redis-backed limiter behind the same
dependency is the documented scale path for multi-replica deployments.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitedError

_WINDOW_SECONDS = 60.0


class InMemoryRateLimiter:
    """Sliding-window counter keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, limit: int, window_seconds: float) -> bool:
        """Record a hit for ``key``; returns False when over the limit."""
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def auth_rate_limit() -> Callable[[Request], Awaitable[None]]:
    """Dependency limiting a route to ``auth_rate_limit_per_minute`` per IP."""

    async def _check(request: Request) -> None:
        limiter: InMemoryRateLimiter = request.app.state.rate_limiter
        limit = get_settings().auth_rate_limit_per_minute
        key = f"{_client_ip(request)}:{request.url.path}"
        if not limiter.check(key, limit=limit, window_seconds=_WINDOW_SECONDS):
            raise RateLimitedError(
                "Too many attempts. Please wait a minute and try again."
            )

    return _check
