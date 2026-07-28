"""Application exception hierarchy.

Services raise these domain-level errors; the centralized handlers in
``app.core.error_handlers`` map them to HTTP responses using the standard
envelope. Routers therefore contain no error-mapping boilerplate.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error carrying an error code and HTTP status."""

    code: str = "APP_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Resource not found"


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409
    message = "Resource conflict"


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422
    message = "Validation failed"


class FileTooLargeError(AppError):
    code = "FILE_TOO_LARGE"
    status_code = 413
    message = "Uploaded file exceeds the maximum allowed size"


class UnsupportedMediaTypeError(AppError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    status_code = 415
    message = "Unsupported file type"


class UpstreamServiceError(AppError):
    code = "UPSTREAM_SERVICE_ERROR"
    status_code = 502
    message = "An upstream service is unavailable"
