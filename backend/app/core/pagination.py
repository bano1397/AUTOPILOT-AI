"""Reusable pagination primitives for collection endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

from app.core.schemas import PageMeta


@dataclass(frozen=True)
class PaginationParams:
    """Validated pagination inputs."""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
) -> PaginationParams:
    """FastAPI dependency producing validated :class:`PaginationParams`."""
    return PaginationParams(page=page, page_size=page_size)


def build_page_meta(pagination: PaginationParams, total: int) -> PageMeta:
    """Compute pagination metadata for a response envelope."""
    pages = (
        (total + pagination.page_size - 1) // pagination.page_size
        if pagination.page_size
        else 0
    )
    return PageMeta(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
        pages=pages,
    )
