"""Notification read/manage use-cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams
from app.features.notifications.models import Notification
from app.features.notifications.repository import NotificationRepository


class NotificationService:
    """List, count, and mark a user's notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = NotificationRepository(session)

    async def list_notifications(
        self, user_id: UUID, pagination: PaginationParams
    ) -> tuple[Sequence[Notification], int]:
        items = await self._repo.list_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit
        )
        total = await self._repo.count_for_user(user_id)
        return items, total

    async def unread_count(self, user_id: UUID) -> int:
        return await self._repo.unread_count(user_id)

    async def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification:
        notification = await self._repo.get(notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotFoundError("Notification not found")
        notification.read = True
        await self._session.commit()
        return notification

    async def mark_all_read(self, user_id: UUID) -> int:
        updated = await self._repo.mark_all_read(user_id)
        await self._session.commit()
        return updated
