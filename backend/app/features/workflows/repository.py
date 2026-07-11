"""Data-access repository for workflow runs and steps."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflows.models import WorkflowRun, WorkflowStep


class WorkflowRunRepository:
    """Persistence operations for workflow runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: WorkflowRun) -> WorkflowRun:
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, run_id: UUID) -> WorkflowRun | None:
        return await self._session.get(WorkflowRun, run_id)

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> Sequence[WorkflowRun]:
        result = await self._session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.user_id == user_id)
            .order_by(WorkflowRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.user_id == user_id)
        )
        return int(result.scalar_one())

    async def add_step(
        self, run_id: UUID, *, position: int, node_name: str, duration_ms: int
    ) -> WorkflowStep:
        step = WorkflowStep(
            run_id=run_id,
            position=position,
            node_name=node_name,
            duration_ms=duration_ms,
        )
        self._session.add(step)
        await self._session.flush()
        return step

    async def list_steps(self, run_id: UUID) -> Sequence[WorkflowStep]:
        result = await self._session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.run_id == run_id)
            .order_by(WorkflowStep.position)
        )
        return result.scalars().all()
