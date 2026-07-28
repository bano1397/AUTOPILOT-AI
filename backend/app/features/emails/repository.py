"""Data access for ingested emails."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.emails.models import Email, EmailStatus


class EmailRepository:
    """Persistence operations for :class:`Email`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, mail: Email) -> Email:
        self._session.add(mail)
        await self._session.flush()
        return mail

    async def get(self, user_id: UUID, email_id: UUID) -> Email | None:
        result = await self._session.execute(
            select(Email).where(Email.id == email_id, Email.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def message_id_exists(self, message_id: str) -> bool:
        result = await self._session.execute(
            select(Email.id).where(Email.message_id == message_id)
        )
        return result.first() is not None

    async def list_paginated(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        status: EmailStatus | None = None,
    ) -> tuple[Sequence[Email], int]:
        filters = [Email.user_id == user_id]
        if status is not None:
            filters.append(Email.status == status)

        items = await self._session.execute(
            select(Email)
            .where(*filters)
            .order_by(Email.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._session.execute(
            select(func.count()).select_from(Email).where(*filters)
        )
        return items.scalars().all(), int(total.scalar_one())
