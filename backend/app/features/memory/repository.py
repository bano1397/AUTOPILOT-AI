"""Data-access repository for long-term memory entries."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.memory.models import MemoryEntry


class MemoryRepository:
    """Persistence operations for :class:`MemoryEntry`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: MemoryEntry) -> MemoryEntry:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get(self, entry_id: UUID) -> MemoryEntry | None:
        return await self._session.get(MemoryEntry, entry_id)

    async def get_many(self, entry_ids: Sequence[UUID]) -> Sequence[MemoryEntry]:
        """Fetch entries by id, in unspecified order.

        Used to hydrate vector hits back into rows; the caller restores
        similarity order, which the database cannot know about.
        """
        if not entry_ids:
            return []
        result = await self._session.execute(
            select(MemoryEntry).where(MemoryEntry.id.in_(entry_ids))
        )
        return result.scalars().all()

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        kind: str | None = None,
    ) -> Sequence[MemoryEntry]:
        query = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if kind is not None:
            query = query.where(MemoryEntry.kind == kind)
        result = await self._session.execute(
            query.order_by(MemoryEntry.created_at.desc()).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: UUID, *, kind: str | None = None) -> int:
        query = (
            select(func.count())
            .select_from(MemoryEntry)
            .where(MemoryEntry.user_id == user_id)
        )
        if kind is not None:
            query = query.where(MemoryEntry.kind == kind)
        result = await self._session.execute(query)
        return int(result.scalar_one())

    async def delete(self, entry: MemoryEntry) -> None:
        await self._session.delete(entry)
        await self._session.flush()
