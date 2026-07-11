"""Scheduler engine.

Wraps APScheduler's ``AsyncIOScheduler``: jobs are code-defined
:class:`JobDefinition` objects registered at app-assembly time; the underlying
scheduler starts inside the application lifespan (it needs a running event
loop). The manager keeps its own registry so a job can also be executed
directly (deterministically) via :meth:`run_job` — used by the admin
"run now" endpoint and by tests.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger("app.scheduler")

# A job coroutine returns a small JSON-friendly summary of what it did.
JobFunc = Callable[[], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class JobDefinition:
    """A code-defined recurring job."""

    id: str
    name: str
    description: str
    func: JobFunc
    hour: int
    minute: int = 0


@dataclass(frozen=True)
class JobInfo:
    """Introspection data for one registered job."""

    id: str
    name: str
    description: str
    next_run_at: datetime | None
    paused: bool


class SchedulerManager:
    """Owns the AsyncIO scheduler and the registry of job definitions."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=UTC)
        self._definitions: dict[str, JobDefinition] = {}

    def register(self, definition: JobDefinition) -> None:
        """Add a job definition and schedule it (daily at hour:minute UTC)."""
        self._definitions[definition.id] = definition

        async def runner() -> None:
            logger.info("scheduler.job_started", extra={"job_id": definition.id})
            try:
                summary = await definition.func()
                logger.info(
                    "scheduler.job_completed",
                    extra={"job_id": definition.id, **summary},
                )
            except Exception:
                logger.exception(
                    "scheduler.job_failed", extra={"job_id": definition.id}
                )

        self._scheduler.add_job(
            runner,
            CronTrigger(hour=definition.hour, minute=definition.minute, timezone=UTC),
            id=definition.id,
            name=definition.name,
        )

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info(
                "scheduler.started", extra={"jobs": sorted(self._definitions)}
            )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def list_jobs(self) -> list[JobInfo]:
        infos: list[JobInfo] = []
        for definition in self._definitions.values():
            job = self._scheduler.get_job(definition.id)
            next_run = getattr(job, "next_run_time", None) if job else None
            infos.append(
                JobInfo(
                    id=definition.id,
                    name=definition.name,
                    description=definition.description,
                    next_run_at=next_run,
                    paused=job is not None and next_run is None,
                )
            )
        return infos

    async def run_job(self, job_id: str) -> dict[str, Any]:
        """Execute a job immediately (outside its schedule) and return its summary."""
        definition = self._definitions.get(job_id)
        if definition is None:
            raise NotFoundError("Scheduled job not found")
        return await definition.func()

    def pause_job(self, job_id: str) -> None:
        if job_id not in self._definitions:
            raise NotFoundError("Scheduled job not found")
        self._scheduler.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        if job_id not in self._definitions:
            raise NotFoundError("Scheduled job not found")
        self._scheduler.resume_job(job_id)
