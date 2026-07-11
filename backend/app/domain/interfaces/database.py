"""Database provider interface (port).

The concrete implementation lives in ``app.infrastructure.database``. The session
type is SQLAlchemy's :class:`AsyncSession`; fully abstracting the ORM session
would add indirection without value, so it is treated as the persistence
contract's currency.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseProvider(Protocol):
    """Owns the async engine and hands out sessions."""

    def session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Return an async context manager yielding a session."""
        ...

    async def health(self) -> bool:
        """Return True if the database is reachable; raise otherwise."""
        ...

    async def create_all(self) -> None:
        """Create all tables from metadata (used in tests; production uses Alembic)."""
        ...

    async def dispose(self) -> None:
        """Dispose of the engine and its connection pool."""
        ...
