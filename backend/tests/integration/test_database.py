"""Integration tests for the database provider and User model."""

from __future__ import annotations

import pytest
from app.features.users.models import User, UserRole
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


async def test_health_returns_true(db: SqlAlchemyDatabaseProvider) -> None:
    assert await db.health() is True


async def test_persist_and_query_user(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(User(email="a@example.com", password_hash="hashed"))
        await session.commit()

    async with db.session() as session:
        result = await session.execute(select(User).where(User.email == "a@example.com"))
        user = result.scalar_one()

    assert user.id is not None
    assert user.role is UserRole.USER  # default applied
    assert user.is_active is True
    assert user.created_at is not None


async def test_email_unique_constraint(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(User(email="dup@example.com", password_hash="h1"))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with db.session() as session:
            session.add(User(email="dup@example.com", password_hash="h2"))
            await session.commit()


async def test_admin_role_persists(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(
            User(email="admin@example.com", password_hash="h", role=UserRole.ADMIN)
        )
        await session.commit()

    async with db.session() as session:
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        assert result.scalar_one().role is UserRole.ADMIN
