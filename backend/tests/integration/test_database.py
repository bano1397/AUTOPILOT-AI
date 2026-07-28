"""Integration tests for the database provider and workspace-identity model."""

from __future__ import annotations

import pytest
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


async def test_health_returns_true(db: SqlAlchemyDatabaseProvider) -> None:
    assert await db.health() is True


async def test_persist_and_query_user(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(User(email="a@example.com"))
        await session.commit()

    async with db.session() as session:
        result = await session.execute(select(User).where(User.email == "a@example.com"))
        user = result.scalar_one()

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None


async def test_email_unique_constraint(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(User(email="dup@example.com"))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with db.session() as session:
            session.add(User(email="dup@example.com"))
            await session.commit()
