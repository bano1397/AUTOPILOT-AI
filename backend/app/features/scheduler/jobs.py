"""Built-in scheduled jobs.

The daily digest composes the platform's existing pieces: it summarizes each
user's last 24 hours (workflow runs, indexed documents) and delivers the
summary through the notification dispatcher (all configured channels).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.interfaces.database import DatabaseProvider
from app.features.documents.models import Document, DocumentStatus
from app.features.notifications.dispatcher import NotificationDispatcher
from app.features.scheduler.manager import JobDefinition, SchedulerManager
from app.features.users.models import User
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus
from app.infrastructure.notifications import build_notification_providers

logger = get_logger("app.scheduler.jobs")

DAILY_DIGEST_JOB_ID = "daily_digest"


class DigestService:
    """Builds and sends the per-user daily activity digest."""

    def __init__(self, db: DatabaseProvider) -> None:
        self._db = db

    async def run(self) -> dict[str, Any]:
        """Send digests to every user with activity; returns a run summary."""
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        dispatcher = NotificationDispatcher(
            self._db, build_notification_providers(get_settings(), self._db)
        )

        sent = 0
        async with self._db.session() as session:
            result = await session.execute(select(User).where(User.is_active.is_(True)))
            users = list(result.scalars().all())

        for user in users:
            summary = await self._user_summary(user.id, cutoff)
            if summary is None:
                continue
            await dispatcher.dispatch(
                user.id, kind="daily_digest", title="Your daily digest", body=summary
            )
            sent += 1

        logger.info("digest.completed", extra={"users": len(users), "sent": sent})
        return {"users_checked": len(users), "digests_sent": sent}

    async def _user_summary(self, user_id: Any, cutoff: datetime) -> str | None:
        """One user's activity line, or None when there was no activity."""
        async with self._db.session() as session:
            completed = await session.scalar(
                select(func.count())
                .select_from(WorkflowRun)
                .where(
                    WorkflowRun.user_id == user_id,
                    WorkflowRun.created_at >= cutoff,
                    WorkflowRun.status == WorkflowRunStatus.COMPLETED,
                )
            )
            failed = await session.scalar(
                select(func.count())
                .select_from(WorkflowRun)
                .where(
                    WorkflowRun.user_id == user_id,
                    WorkflowRun.created_at >= cutoff,
                    WorkflowRun.status == WorkflowRunStatus.FAILED,
                )
            )
            documents = await session.scalar(
                select(func.count())
                .select_from(Document)
                .where(
                    Document.user_id == user_id,
                    Document.created_at >= cutoff,
                    Document.status == DocumentStatus.INDEXED,
                )
            )

        completed = completed or 0
        failed = failed or 0
        documents = documents or 0
        if completed == 0 and failed == 0 and documents == 0:
            return None

        parts = [f"{completed} workflow run(s) completed"]
        if failed:
            parts.append(f"{failed} failed")
        if documents:
            parts.append(f"{documents} document(s) indexed")
        return "In the last 24 hours: " + ", ".join(parts) + "."


def register_scheduled_jobs(
    manager: SchedulerManager, resolve_db: Callable[[], DatabaseProvider]
) -> None:
    """Register the built-in jobs; dependencies resolve at run time."""
    settings = get_settings()

    async def daily_digest() -> dict[str, Any]:
        return await DigestService(resolve_db()).run()

    manager.register(
        JobDefinition(
            id=DAILY_DIGEST_JOB_ID,
            name="Daily digest",
            description=(
                "Summarizes each user's last 24 hours (workflow runs, indexed "
                "documents) and sends it over the configured channels."
            ),
            func=daily_digest,
            hour=settings.digest_hour,
        )
    )
