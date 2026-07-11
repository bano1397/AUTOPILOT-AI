"""Workflow execution and query use-cases.

``WorkflowExecutor`` wraps any compiled LangGraph graph: it persists a run row,
records each node as a step (with timing) while the graph streams, publishes the
workflow lifecycle events, and finalizes the run as completed or failed.

Sessions are short-lived (one per write): the AI-execution recorder also writes
during graph execution, and holding a transaction open across LLM calls would
invite SQLite lock contention.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.domain.events import (
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
    WorkflowStepCompleted,
)
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.event_bus import EventBus
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus, WorkflowStep
from app.features.workflows.repository import WorkflowRunRepository

logger = get_logger("app.features.workflows")

OutputBuilder = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ExecutionOutcome:
    """Result of executing (or resuming) a workflow graph."""

    run_id: UUID
    state: dict[str, Any] = field(default_factory=dict)
    interrupted: bool = False
    interrupt_payload: dict[str, Any] | None = None


def _interrupt_payload(node_update: Any) -> dict[str, Any] | None:
    """Extract the payload passed to ``interrupt()`` from a stream update."""
    try:
        value = node_update[0].value
        return dict(value) if isinstance(value, dict) else {"value": value}
    except Exception:  # pragma: no cover - defensive against shape changes
        return None


class WorkflowExecutor:
    """Executes a compiled graph as a persistent, observable workflow run."""

    def __init__(self, db: DatabaseProvider, bus: EventBus) -> None:
        self._db = db
        self._bus = bus

    async def execute(
        self,
        *,
        user_id: UUID,
        workflow_name: str,
        graph: Any,
        initial_state: Mapping[str, Any],
        input_payload: dict[str, Any] | None = None,
        output_builder: OutputBuilder | None = None,
    ) -> ExecutionOutcome:
        """Run ``graph`` as a persistent workflow run.

        A graph interrupt (approval gate) leaves the run ``awaiting_approval``;
        failures are recorded on the run and re-raised so API error handling
        applies unchanged.
        """
        run_id = await self._create_run(user_id, workflow_name, input_payload)
        await self._bus.publish(
            WorkflowStarted(
                run_id=str(run_id), workflow_name=workflow_name, user_id=str(user_id)
            )
        )

        state: dict[str, Any] = dict(initial_state)
        started = perf_counter()
        try:
            interrupted, payload = await self._stream(
                graph, dict(initial_state), run_id, start_position=0, state=state
            )
        except Exception as exc:
            await self._fail(run_id, workflow_name, exc, started)
            raise

        total_ms = int((perf_counter() - started) * 1000)
        if interrupted:
            await self._finish(
                run_id,
                status=WorkflowRunStatus.AWAITING_APPROVAL,
                duration_ms=total_ms,
                ended=False,
            )
            return ExecutionOutcome(
                run_id, state, interrupted=True, interrupt_payload=payload
            )

        output = output_builder(state) if output_builder else None
        await self._finish(
            run_id,
            status=WorkflowRunStatus.COMPLETED,
            output=output,
            duration_ms=total_ms,
        )
        await self._bus.publish(WorkflowCompleted(run_id=str(run_id)))
        return ExecutionOutcome(run_id, state)

    async def resume(
        self,
        *,
        run_id: UUID,
        graph: Any,
        resume_value: str,
        output_builder: OutputBuilder | None = None,
    ) -> ExecutionOutcome:
        """Resume an interrupted run from its checkpoint and finalize it."""
        start_position, prior_ms = await self._run_progress(run_id)
        state: dict[str, Any] = {}
        started = perf_counter()
        try:
            interrupted, payload = await self._stream(
                graph,
                Command(resume=resume_value),
                run_id,
                start_position=start_position,
                state=state,
            )
        except Exception as exc:
            await self._fail(run_id, "resume", exc, started, prior_ms=prior_ms)
            raise

        # The stream only carries post-interrupt updates; the checkpoint holds
        # the complete state.
        snapshot = await graph.aget_state(self._config(run_id))
        full_state: dict[str, Any] = dict(snapshot.values) if snapshot else state

        total_ms = prior_ms + int((perf_counter() - started) * 1000)
        if interrupted:  # a further gate paused the run again
            await self._finish(
                run_id,
                status=WorkflowRunStatus.AWAITING_APPROVAL,
                duration_ms=total_ms,
                ended=False,
            )
            return ExecutionOutcome(
                run_id, full_state, interrupted=True, interrupt_payload=payload
            )

        output = output_builder(full_state) if output_builder else None
        await self._finish(
            run_id,
            status=WorkflowRunStatus.COMPLETED,
            output=output,
            duration_ms=total_ms,
        )
        await self._bus.publish(WorkflowCompleted(run_id=str(run_id)))
        return ExecutionOutcome(run_id, full_state)

    @staticmethod
    def _config(run_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(run_id)}}

    async def _stream(
        self,
        graph: Any,
        input_object: Any,
        run_id: UUID,
        *,
        start_position: int,
        state: dict[str, Any],
    ) -> tuple[bool, dict[str, Any] | None]:
        """Drive the graph, recording each node as a step; detect interrupts."""
        position = start_position
        interrupted = False
        payload: dict[str, Any] | None = None
        step_started = perf_counter()
        async for update in graph.astream(
            input_object, config=self._config(run_id), stream_mode="updates"
        ):
            for node_name, node_update in update.items():
                if node_name == "__interrupt__":
                    interrupted = True
                    payload = _interrupt_payload(node_update)
                    continue
                duration_ms = int((perf_counter() - step_started) * 1000)
                if isinstance(node_update, dict):
                    state.update(node_update)
                await self._record_step(
                    run_id,
                    position=position,
                    node_name=str(node_name),
                    duration_ms=duration_ms,
                )
                await self._bus.publish(
                    WorkflowStepCompleted(
                        run_id=str(run_id),
                        node_name=str(node_name),
                        duration_ms=duration_ms,
                    )
                )
                position += 1
                step_started = perf_counter()
        return interrupted, payload

    async def _fail(
        self,
        run_id: UUID,
        workflow_name: str,
        exc: Exception,
        started: float,
        *,
        prior_ms: int = 0,
    ) -> None:
        total_ms = prior_ms + int((perf_counter() - started) * 1000)
        await self._finish(
            run_id,
            status=WorkflowRunStatus.FAILED,
            error=str(exc)[:2000],
            duration_ms=total_ms,
        )
        await self._bus.publish(WorkflowFailed(run_id=str(run_id), error=str(exc)[:500]))
        logger.warning(
            "workflow.failed", extra={"run_id": str(run_id), "workflow": workflow_name}
        )

    async def _run_progress(self, run_id: UUID) -> tuple[int, int]:
        """Return (next step position, accumulated duration) for a run."""
        async with self._db.session() as session:
            repo = WorkflowRunRepository(session)
            steps = await repo.list_steps(run_id)
            run = await repo.get(run_id)
            return len(steps), (run.duration_ms or 0) if run else 0

    async def _create_run(
        self, user_id: UUID, workflow_name: str, input_payload: dict[str, Any] | None
    ) -> UUID:
        async with self._db.session() as session:
            run = await WorkflowRunRepository(session).add(
                WorkflowRun(
                    user_id=user_id, workflow_name=workflow_name, input=input_payload
                )
            )
            await session.commit()
            return run.id

    async def _record_step(
        self, run_id: UUID, *, position: int, node_name: str, duration_ms: int
    ) -> None:
        async with self._db.session() as session:
            await WorkflowRunRepository(session).add_step(
                run_id, position=position, node_name=node_name, duration_ms=duration_ms
            )
            await session.commit()

    async def _finish(
        self,
        run_id: UUID,
        *,
        status: WorkflowRunStatus,
        duration_ms: int,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        ended: bool = True,
    ) -> None:
        async with self._db.session() as session:
            run = await WorkflowRunRepository(session).get(run_id)
            if run is None:  # pragma: no cover - the run was just created
                return
            run.status = status
            run.output = output
            run.error = error
            run.ended_at = datetime.now(UTC) if ended else None
            run.duration_ms = duration_ms
            await session.commit()


class WorkflowQueryService:
    """Read operations over a user's workflow runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = WorkflowRunRepository(session)

    async def list_runs(
        self, user_id: UUID, pagination: PaginationParams
    ) -> tuple[Sequence[WorkflowRun], int]:
        items = await self._repo.list_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit
        )
        total = await self._repo.count_for_user(user_id)
        return items, total

    async def get_run(
        self, user_id: UUID, run_id: UUID
    ) -> tuple[WorkflowRun, Sequence[WorkflowStep]]:
        run = await self._repo.get(run_id)
        if run is None or run.user_id != user_id:
            raise NotFoundError("Workflow run not found")
        steps = await self._repo.list_steps(run_id)
        return run, steps
