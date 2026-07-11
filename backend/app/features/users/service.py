"""User management use-cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams
from app.features.users.models import User
from app.features.users.repository import UserRepository


class UserService:
    """Read operations over platform users (admin-facing)."""

    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)

    async def list_users(self, pagination: PaginationParams) -> tuple[Sequence[User], int]:
        items = await self._users.list_paginated(
            offset=pagination.offset, limit=pagination.limit
        )
        total = await self._users.count()
        return items, total

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user
