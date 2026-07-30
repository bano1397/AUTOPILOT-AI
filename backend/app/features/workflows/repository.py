"""Data-access repositories for workflow definitions, versions, runs, steps."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowVersion,
)


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


class WorkflowDefinitionRepository:
    """Persistence operations for definitions and their versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- definitions ---------------------------------------------------------

    async def add(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        self._session.add(definition)
        await self._session.flush()
        return definition

    async def get(self, definition_id: UUID) -> WorkflowDefinition | None:
        return await self._session.get(WorkflowDefinition, definition_id)

    async def get_by_name(self, name: str) -> WorkflowDefinition | None:
        result = await self._session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.name == name)
        )
        return result.scalar_one_or_none()

    async def list_definitions(
        self, *, offset: int, limit: int
    ) -> Sequence[WorkflowDefinition]:
        result = await self._session.execute(
            select(WorkflowDefinition)
            .order_by(WorkflowDefinition.name)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_definitions(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(WorkflowDefinition)
        )
        return int(result.scalar_one())

    # -- versions ------------------------------------------------------------

    async def add_version(self, version: WorkflowVersion) -> WorkflowVersion:
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_version(self, version_id: UUID) -> WorkflowVersion | None:
        return await self._session.get(WorkflowVersion, version_id)

    async def list_versions(self, definition_id: UUID) -> Sequence[WorkflowVersion]:
        result = await self._session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.definition_id == definition_id)
            .order_by(WorkflowVersion.version)
        )
        return result.scalars().all()

    async def active_version(self, definition_id: UUID) -> WorkflowVersion | None:
        result = await self._session.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.definition_id == definition_id,
                WorkflowVersion.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def next_version_number(self, definition_id: UUID) -> int:
        result = await self._session.execute(
            select(func.max(WorkflowVersion.version)).where(
                WorkflowVersion.definition_id == definition_id
            )
        )
        return int(result.scalar() or 0) + 1

    async def deactivate_all(self, definition_id: UUID) -> None:
        """Clear the active flag across a definition's versions.

        Called immediately before setting the new one in the same transaction,
        so "exactly one active" never appears violated to another reader.
        """
        for version in await self.list_versions(definition_id):
            if version.is_active:
                version.is_active = False
        await self._session.flush()

    # -- runs by version -----------------------------------------------------

    async def list_runs_for_version(
        self, version_id: UUID, *, offset: int, limit: int
    ) -> Sequence[WorkflowRun]:
        result = await self._session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.workflow_version_id == version_id)
            .order_by(WorkflowRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_runs_for_version(self, version_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.workflow_version_id == version_id)
        )
        return int(result.scalar_one())
