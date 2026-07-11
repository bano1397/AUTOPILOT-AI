"""Task use-cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams
from app.features.tasks.models import Task, TaskPriority, TaskStatus
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import TaskCreateRequest, TaskUpdateRequest


class TaskService:
    """CRUD over a user's tasks (used by the API and the planner agent)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TaskRepository(session)

    async def create(self, user_id: UUID, payload: TaskCreateRequest) -> Task:
        task = await self._repo.add(
            Task(
                user_id=user_id,
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                due_date=payload.due_date,
            )
        )
        await self._session.commit()
        return task

    async def create_planned(
        self, user_id: UUID, items: Sequence[tuple[str, str, TaskPriority]]
    ) -> list[Task]:
        """Persist planner-generated tasks: (title, description, priority)."""
        tasks = [
            Task(
                user_id=user_id,
                title=title[:200],
                description=description[:2000],
                priority=priority,
                source="planner",
            )
            for title, description, priority in items
        ]
        await self._repo.add_many(tasks)
        await self._session.commit()
        return tasks

    async def list_tasks(
        self,
        user_id: UUID,
        pagination: PaginationParams,
        status: TaskStatus | None = None,
    ) -> tuple[Sequence[Task], int]:
        items = await self._repo.list_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit, status=status
        )
        total = await self._repo.count_for_user(user_id, status=status)
        return items, total

    async def update(
        self, user_id: UUID, task_id: UUID, payload: TaskUpdateRequest
    ) -> Task:
        task = await self._get_owned(user_id, task_id)
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        await self._session.commit()
        # ``updated_at`` is server-onupdate and expires on flush; refresh it
        # explicitly or serialization lazy-loads outside greenlet context.
        await self._session.refresh(task)
        return task

    async def delete(self, user_id: UUID, task_id: UUID) -> None:
        task = await self._get_owned(user_id, task_id)
        await self._repo.delete(task)
        await self._session.commit()

    async def _get_owned(self, user_id: UUID, task_id: UUID) -> Task:
        task = await self._repo.get(task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("Task not found")
        return task
