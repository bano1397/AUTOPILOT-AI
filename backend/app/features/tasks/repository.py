"""Data-access repository for tasks."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tasks.models import Task, TaskStatus


class TaskRepository:
    """Persistence operations for :class:`Task`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> Task:
        self._session.add(task)
        await self._session.flush()
        return task

    async def add_many(self, tasks: Sequence[Task]) -> Sequence[Task]:
        self._session.add_all(tasks)
        await self._session.flush()
        return tasks

    async def get(self, task_id: UUID) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        status: TaskStatus | None = None,
    ) -> Sequence[Task]:
        query = select(Task).where(Task.user_id == user_id)
        if status is not None:
            query = query.where(Task.status == status)
        result = await self._session.execute(
            query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(
        self, user_id: UUID, *, status: TaskStatus | None = None
    ) -> int:
        query = select(func.count()).select_from(Task).where(Task.user_id == user_id)
        if status is not None:
            query = query.where(Task.status == status)
        result = await self._session.execute(query)
        return int(result.scalar_one())

    async def delete(self, task: Task) -> None:
        await self._session.delete(task)
        await self._session.flush()
