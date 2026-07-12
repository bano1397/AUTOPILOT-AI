"""Async engine and session factory builders.

Kept separate from the provider so both the application and the Alembic migration
environment can construct engines from the same configuration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def asyncpg_connect_args(database_url: str) -> dict[str, Any]:
    """Connect args for asyncpg on transaction-pooling proxies (e.g. Neon's
    PgBouncer endpoint), which reject cached prepared statements. Empty for
    every other driver (SQLite, etc.)."""
    if database_url.startswith("postgresql+asyncpg"):
        return {"statement_cache_size": 0}
    return {}


def build_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for the given database URL."""
    return create_async_engine(
        database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
        connect_args=asyncpg_connect_args(database_url),
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to ``engine``."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
