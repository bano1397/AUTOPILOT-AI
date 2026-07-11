"""Data-access repository for notifications."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.notifications.models import Notification


class NotificationRepository:
    """Persistence operations for :class:`Notification`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, notification_id: UUID) -> Notification | None:
        return await self._session.get(Notification, notification_id)

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> Sequence[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
        )
        return int(result.scalar_one())

    async def unread_count(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read.is_(False))
        )
        return int(result.scalar_one())

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read.is_(False))
            .values(read=True)
        )
        # execute() on an UPDATE returns a CursorResult; the base Result type
        # doesn't declare rowcount, hence the getattr.
        return int(getattr(result, "rowcount", 0) or 0)
