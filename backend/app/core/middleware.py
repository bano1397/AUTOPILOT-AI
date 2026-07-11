"""HTTP middleware.

``CorrelationIdMiddleware`` assigns a correlation id to every request (reusing
an inbound ``X-Request-ID`` header when present), makes it available to the
logging layer via a ``ContextVar``, echoes it back on the response, and emits a
structured access log line with the request duration.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_var, get_logger

REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger("app.request")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response.

    HSTS is emitted only in production (behind TLS); sending it over plain
    HTTP in development would be meaningless at best.
    """

    def __init__(self, app: object, *, hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # A JSON API serves no active content; lock the CSP down completely.
        # The interactive docs are real HTML pages and need their own assets.
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if self._hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to the request/response and log completion."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = correlation_id_var.set(correlation_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers[REQUEST_ID_HEADER] = correlation_id
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            correlation_id_var.reset(token)
