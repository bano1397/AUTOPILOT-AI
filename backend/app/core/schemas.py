"""Standard API response envelope.

Business endpoints return :class:`ApiResponse`; errors are rendered as
:class:`ErrorResponse` by the centralized exception handlers. Infrastructure
probes (health/readiness) intentionally return raw payloads.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """Successful response wrapper."""

    success: bool = True
    data: DataT
    meta: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    """Machine-readable error information."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response wrapper."""

    success: bool = False
    error: ErrorDetail


class MessageResponse(BaseModel):
    """Generic human-readable confirmation payload."""

    message: str


class PageMeta(BaseModel):
    """Pagination metadata carried in a list response's ``meta`` field."""

    page: int
    page_size: int
    total: int
    pages: int
