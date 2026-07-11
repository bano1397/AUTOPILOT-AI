"""SQLAlchemy async implementation of :class:`DatabaseProvider`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# Import the aggregated models module so Base.metadata is fully populated
# before ``create_all`` is ever called.
from app.database import models as _models
from app.database.engine import build_engine, build_sessionmaker
from app.platform.registry import register_provider

Base = _models.Base


@register_provider(kind="database", name="sqlalchemy")
class SqlAlchemyDatabaseProvider:
    """Owns the async engine/session factory for a SQLAlchemy database."""

    name = "sqlalchemy"

    def __init__(self, *, database_url: str, echo: bool = False) -> None:
        self._engine: AsyncEngine = build_engine(database_url, echo=echo)
        self._sessionmaker = build_sessionmaker(self._engine)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session, rolling back on error and always closing."""
        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def health(self) -> bool:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def create_all(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()
