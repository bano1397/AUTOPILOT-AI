"""Integration tests for the scheduler and the daily digest job."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.core.security import hash_password
from app.features.documents.models import Document, DocumentStatus
from app.features.scheduler.jobs import DAILY_DIGEST_JOB_ID
from app.features.users.models import User, UserRole
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_ADMIN = ("admin@example.com", "adminpass1")
_USER = ("user@example.com", "userpass12")


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


async def _seed_and_login(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> str:
    async with db.session() as session:
        session.add(
            User(email=email, password_hash=hash_password(password), role=role)
        )
        await session.commit()
    response = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(response.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_activity(db: SqlAlchemyDatabaseProvider, email: str) -> None:
    """Give a user one completed run, one failed run, and one indexed document."""
    async with db.session() as session:
        user = User(email=email, password_hash=hash_password("password12"))
        session.add(user)
        await session.flush()
        session.add(
            WorkflowRun(
                user_id=user.id,
                workflow_name="agents.ask",
                status=WorkflowRunStatus.COMPLETED,
            )
        )
        session.add(
            WorkflowRun(
                user_id=user.id,
                workflow_name="agents.ask",
                status=WorkflowRunStatus.FAILED,
                error="boom",
            )
        )
        session.add(
            Document(
                user_id=user.id,
                filename="notes.txt",
                mime_type="text/plain",
                size_bytes=10,
                status=DocumentStatus.INDEXED,
                storage_path="x/y.txt",
                doc_metadata={},
            )
        )
        await session.commit()


async def test_jobs_listing_is_admin_only(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    user_token = await _seed_and_login(api, db, *_USER)

    anonymous = await api.get("/api/v1/scheduler/jobs")
    non_admin = await api.get("/api/v1/scheduler/jobs", headers=_auth(user_token))

    assert anonymous.status_code == 401
    assert non_admin.status_code == 403


async def test_jobs_listing_shows_daily_digest(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ADMIN, role=UserRole.ADMIN)

    response = await api.get("/api/v1/scheduler/jobs", headers=_auth(token))

    assert response.status_code == 200
    jobs = {job["id"]: job for job in response.json()["data"]}
    digest = jobs[DAILY_DIGEST_JOB_ID]
    assert digest["name"] == "Daily digest"
    assert digest["next_run_at"] is not None
    assert digest["paused"] is False


async def test_run_digest_sends_notifications_for_active_users(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    admin_token = await _seed_and_login(api, db, *_ADMIN, role=UserRole.ADMIN)
    await _seed_activity(db, "busy@example.com")

    response = await api.post(
        f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/run", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    summary = response.json()["data"]["summary"]
    assert summary["users_checked"] == 2  # admin + busy user
    assert summary["digests_sent"] == 1  # only the user with activity

    # The digest landed as an in-app notification with the right numbers.
    busy_login = await api.post(
        "/api/v1/auth/login",
        json={"email": "busy@example.com", "password": "password12"},
    )
    busy_token = str(busy_login.json()["data"]["access_token"])
    notifications = await api.get("/api/v1/notifications", headers=_auth(busy_token))
    items = notifications.json()["data"]
    assert len(items) == 1
    assert items[0]["type"] == "daily_digest"
    assert "1 workflow run(s) completed" in items[0]["body"]
    assert "1 failed" in items[0]["body"]
    assert "1 document(s) indexed" in items[0]["body"]

    # The quiet admin got nothing.
    own = await api.get("/api/v1/notifications", headers=_auth(admin_token))
    assert own.json()["data"] == []


async def test_pause_and_resume_job(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ADMIN, role=UserRole.ADMIN)

    paused = await api.post(
        f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/pause", headers=_auth(token)
    )
    assert paused.status_code == 200
    listing = await api.get("/api/v1/scheduler/jobs", headers=_auth(token))
    assert listing.json()["data"][0]["paused"] is True

    resumed = await api.post(
        f"/api/v1/scheduler/jobs/{DAILY_DIGEST_JOB_ID}/resume", headers=_auth(token)
    )
    assert resumed.status_code == 200
    listing = await api.get("/api/v1/scheduler/jobs", headers=_auth(token))
    assert listing.json()["data"][0]["paused"] is False


async def test_unknown_job_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ADMIN, role=UserRole.ADMIN)

    response = await api.post(
        "/api/v1/scheduler/jobs/nope/run", headers=_auth(token)
    )

    assert response.status_code == 404
