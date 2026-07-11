"""Data-access repository for users."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User


class UserRepository:
    """Persistence operations for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def email_exists(self, email: str) -> bool:
        result = await self._session.execute(select(User.id).where(User.email == email))
        return result.first() is not None

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def list_paginated(self, *, offset: int, limit: int) -> Sequence[User]:
        result = await self._session.execute(
            select(User).order_by(User.created_at).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())
