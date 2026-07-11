"""Centralized exception handlers.

Every error is rendered using the standard :class:`ErrorResponse` envelope, so
clients get a consistent shape. The active request's correlation id is included
so users can reference failures in support requests.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logging import correlation_id_var, get_logger
from app.core.schemas import ErrorDetail, ErrorResponse

logger = get_logger("app.errors")


def _render(status_code: int, code: str, message: str, details: dict[str, object]) -> JSONResponse:
    correlation_id = correlation_id_var.get()
    if correlation_id:
        details = {**details, "correlation_id": correlation_id}
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the application's exception handlers to ``app``."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error", extra={"code": exc.code, "status_code": exc.status_code}
        )
        return _render(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _render(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return _render(500, "INTERNAL_ERROR", "Internal server error", {})
