"""Fixtures for database integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[SqlAlchemyDatabaseProvider]:
    """Provide an isolated, file-backed SQLite database with the schema created."""
    db_path = (tmp_path / "test.db").as_posix()
    provider = SqlAlchemyDatabaseProvider(database_url=f"sqlite+aiosqlite:///{db_path}")
    await provider.create_all()
    try:
        yield provider
    finally:
        await provider.dispose()
