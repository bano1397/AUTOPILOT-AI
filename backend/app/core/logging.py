"""Structured logging setup.

Provides JSON (production) and human-readable console (development) formatters,
plus a correlation-id ``ContextVar`` that is injected into every log record so a
single request can be traced across services and, later, AI executions.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import LogFormat, Settings

# Correlation id for the in-flight request; set by CorrelationIdMiddleware.
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Standard ``LogRecord`` attributes that should not be treated as user "extras".
_RESERVED_ATTRS: frozenset[str] = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = correlation_id_var.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Attach any structured extras passed via ``logger.info(..., extra={...})``.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Concise, readable formatter for local development."""

    _FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        correlation_id = correlation_id_var.get()
        return f"{base} [cid={correlation_id}]" if correlation_id else base


def setup_logging(settings: Settings) -> None:
    """Configure the root logger and align uvicorn loggers with our handler.

    Idempotent: repeated calls replace existing handlers rather than stacking.
    """
    formatter: logging.Formatter = (
        JsonFormatter() if settings.log_format is LogFormat.JSON else ConsoleFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Route uvicorn's own loggers through our handler for consistent output.
    for uvicorn_logger in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(uvicorn_logger)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
