"""Integration tests for the scheduler and the daily digest job.

Endpoints are open (``docs/COMPLETION_PLAN.md`` §3), so the former admin-gating
cases are replaced by one open-access check. Digest behavior — who gets a digest
and what it says — is unchanged and still the substance of this file.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest_asyncio
from app.features.documents.models import Document, DocumentStatus
from app.features.scheduler.jobs import DAILY_DIGEST_JOB_ID
from app.features.users.models import User
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import workspace_user_id


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    # The lifespan doesn't run under ASGITransport; start the scheduler here
    # so job introspection (next run, pause/resume) behaves as in production.
    app.state.scheduler.start()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.state.scheduler.shutdown()


async def _seed_quiet_user(db: SqlAlchemyDatabaseProvider) -> None:
    """A second user with no activity — the digest must skip them."""
    async with db.session() as session:
        session.add(User(email="quiet@example.com"))
        await session.commit()


async def _seed_activity(db: SqlAlchemyDatabaseProvider, user_id: UUID) -> None:
    """One completed run, one failed run, and one indexed document."""
    async with db.session() as session:
        session.add(
            WorkflowRun(
                user_id=user_id,
                workflow_name="agents.ask",
                status=WorkflowRunStatus.COMPLETED,
            )
        )
        session.add(
            WorkflowRun(
                user_id=user_id,
                workflow_name="agents.ask",
                status=WorkflowRunStatus.FAILED,
                error="boom",
            )
        )
        session.add(
            Document(
                user_id=user_id,
                filename="notes.txt",
                mime_type="text/plain",
                size_bytes=10,
                status=DocumentStatus.INDEXED,
                storage_path="x/y.txt",
                doc_metadata={},
            )
        )
        await session.commit()


async def test_jobs_listing_is_open(api: AsyncClient) -> None:
    response = await api.get("/api/v1/scheduler/jobs")

    assert response.status_code == 200
    assert response.json()["success"] is True


async def test_jobs_listing_shows_daily_digest(api: AsyncClient) -> None:
    response = await api.get("/api/v1/scheduler/jobs")

    assert response.status_code == 200
    jobs = {job["id"]: job for job in response.json()["data"]}
    digest = jobs[DAILY_DIGEST_JOB_ID]
    assert digest["name"] == "Daily digest"
    assert digest["next_run_at"] is not None
    assert digest["paused"] is False


async def test_run_digest_sends_notifications_only_for_active_users(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    workspace_id = await workspace_user_id(db)
    await _seed_activity(db, workspace_id)
    await _seed_quiet_user(db)

    response = await api.post(f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/run")

    assert response.status_code == 200
    summary = response.json()["data"]["summary"]
    assert summary["users_checked"] == 2  # workspace identity + quiet user
    assert summary["digests_sent"] == 1  # only the one with activity

    # The digest landed as an in-app notification with the right numbers. The
    # request runs as the workspace identity, so this reads its own inbox.
    notifications = await api.get("/api/v1/notifications")
    items = notifications.json()["data"]
    assert len(items) == 1
    assert items[0]["type"] == "daily_digest"
    assert "1 workflow run(s) completed" in items[0]["body"]
    assert "1 failed" in items[0]["body"]
    assert "1 document(s) indexed" in items[0]["body"]


async def test_run_digest_with_no_activity_sends_nothing(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await workspace_user_id(db)

    response = await api.post(f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/run")

    assert response.status_code == 200
    assert response.json()["data"]["summary"]["digests_sent"] == 0
    assert (await api.get("/api/v1/notifications")).json()["data"] == []


async def test_pause_and_resume_job(api: AsyncClient) -> None:
    paused = await api.post(f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/pause")
    assert paused.status_code == 200
    listing = await api.get("/api/v1/scheduler/jobs")
    assert listing.json()["data"][0]["paused"] is True

    resumed = await api.post(f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/resume")
    assert resumed.status_code == 200
    listing = await api.get("/api/v1/scheduler/jobs")
    assert listing.json()["data"][0]["paused"] is False


async def test_unknown_job_returns_404(api: AsyncClient) -> None:
    response = await api.post("/api/v1/scheduler/jobs/nope/run")

    assert response.status_code == 404
