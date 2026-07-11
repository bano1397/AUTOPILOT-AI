"""Analytics use-cases: aggregate AI-usage metrics and entity inventory.

AI metrics (totals, per-feature/model breakdowns, and the daily time series)
are windowed to the requested number of days and scoped to the caller. Entity
counts are current-state inventory (all-time). All aggregation runs in SQL; the
only Python-side work is filling gaps in the time series.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.analytics.schemas import (
    AnalyticsOverviewRead,
    EntityCountsRead,
    FeatureStatRead,
    ModelStatRead,
    StatusCountRead,
    TimeseriesPointRead,
    TotalsRead,
)
from app.features.documents.models import Document, DocumentStatus
from app.features.tasks.models import Task
from app.features.workflows.models import WorkflowRun
from app.platform.observability.models import AiExecution

_TOP_N = 10


class AnalyticsService:
    """Read-only aggregation over the caller's AI executions and entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def overview(self, user_id: UUID, *, days: int) -> AnalyticsOverviewRead:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return AnalyticsOverviewRead(
            days=days,
            totals=await self._totals(user_id, cutoff),
            by_feature=await self._by_feature(user_id, cutoff),
            by_model=await self._by_model(user_id, cutoff),
            timeseries=await self._timeseries(user_id, days),
            entities=await self._entities(user_id),
        )

    async def _totals(self, user_id: UUID, cutoff: datetime) -> TotalsRead:
        row = (
            await self._session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(AiExecution.prompt_tokens), 0),
                    func.coalesce(func.sum(AiExecution.completion_tokens), 0),
                    func.coalesce(func.sum(AiExecution.cost_usd), 0.0),
                    func.coalesce(func.avg(AiExecution.duration_ms), 0.0),
                    func.coalesce(
                        func.sum(case((AiExecution.error.is_not(None), 1), else_=0)), 0
                    ),
                ).where(
                    AiExecution.user_id == user_id, AiExecution.created_at >= cutoff
                )
            )
        ).one()
        executions = int(row[0])
        prompt_tokens = int(row[1])
        completion_tokens = int(row[2])
        errors = int(row[5])
        return TotalsRead(
            executions=executions,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=round(float(row[3]), 6),
            avg_duration_ms=int(row[4]),
            errors=errors,
            error_rate=round(errors / executions, 4) if executions else 0.0,
        )

    async def _by_feature(
        self, user_id: UUID, cutoff: datetime
    ) -> list[FeatureStatRead]:
        tokens = AiExecution.prompt_tokens + AiExecution.completion_tokens
        rows = (
            await self._session.execute(
                select(
                    AiExecution.feature,
                    func.count(),
                    func.coalesce(func.sum(tokens), 0),
                    func.coalesce(func.sum(AiExecution.cost_usd), 0.0),
                )
                .where(AiExecution.user_id == user_id, AiExecution.created_at >= cutoff)
                .group_by(AiExecution.feature)
                .order_by(func.count().desc())
                .limit(_TOP_N)
            )
        ).all()
        return [
            FeatureStatRead(
                feature=str(row[0]),
                executions=int(row[1]),
                total_tokens=int(row[2]),
                cost_usd=round(float(row[3]), 6),
            )
            for row in rows
        ]

    async def _by_model(self, user_id: UUID, cutoff: datetime) -> list[ModelStatRead]:
        tokens = AiExecution.prompt_tokens + AiExecution.completion_tokens
        rows = (
            await self._session.execute(
                select(
                    AiExecution.model,
                    func.count(),
                    func.coalesce(func.sum(tokens), 0),
                    func.coalesce(func.sum(AiExecution.cost_usd), 0.0),
                )
                .where(AiExecution.user_id == user_id, AiExecution.created_at >= cutoff)
                .group_by(AiExecution.model)
                .order_by(func.count().desc())
                .limit(_TOP_N)
            )
        ).all()
        return [
            ModelStatRead(
                model=str(row[0]),
                executions=int(row[1]),
                total_tokens=int(row[2]),
                cost_usd=round(float(row[3]), 6),
            )
            for row in rows
        ]

    async def _timeseries(
        self, user_id: UUID, days: int
    ) -> list[TimeseriesPointRead]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        day = func.date(AiExecution.created_at)
        tokens = AiExecution.prompt_tokens + AiExecution.completion_tokens
        rows = (
            await self._session.execute(
                select(
                    day,
                    func.count(),
                    func.coalesce(func.sum(tokens), 0),
                    func.coalesce(func.sum(AiExecution.cost_usd), 0.0),
                )
                .where(AiExecution.user_id == user_id, AiExecution.created_at >= cutoff)
                .group_by(day)
            )
        ).all()
        by_date = {
            str(row[0]): (int(row[1]), int(row[2]), round(float(row[3]), 6))
            for row in rows
        }

        # Fill every day in the window so the chart has no gaps.
        today = datetime.now(UTC).date()
        points: list[TimeseriesPointRead] = []
        for offset in range(days - 1, -1, -1):
            key = (today - timedelta(days=offset)).isoformat()
            executions, total_tokens, cost = by_date.get(key, (0, 0, 0.0))
            points.append(
                TimeseriesPointRead(
                    date=key,
                    executions=executions,
                    total_tokens=total_tokens,
                    cost_usd=cost,
                )
            )
        return points

    async def _entities(self, user_id: UUID) -> EntityCountsRead:
        run_rows = (
            await self._session.execute(
                select(WorkflowRun.status, func.count())
                .where(WorkflowRun.user_id == user_id)
                .group_by(WorkflowRun.status)
            )
        ).all()
        task_rows = (
            await self._session.execute(
                select(Task.status, func.count())
                .where(Task.user_id == user_id)
                .group_by(Task.status)
            )
        ).all()
        documents_indexed = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.user_id == user_id,
                    Document.status == DocumentStatus.INDEXED,
                )
            )
            or 0
        )
        return EntityCountsRead(
            workflow_runs=[
                StatusCountRead(status=row[0].value, count=int(row[1]))
                for row in run_rows
            ],
            documents_indexed=documents_indexed,
            tasks=[
                StatusCountRead(status=row[0].value, count=int(row[1]))
                for row in task_rows
            ],
        )
