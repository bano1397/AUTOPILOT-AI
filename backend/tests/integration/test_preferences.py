"""Integration tests for instance-wide workspace preferences."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.features.preferences.models import WorkspacePreferences
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select


@pytest_asyncio.fixture
async def api(app: FastAPI, db: SqlAlchemyDatabaseProvider) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _row_count(db: SqlAlchemyDatabaseProvider) -> int:
    async with db.session() as session:
        result = await session.execute(
            select(func.count()).select_from(WorkspacePreferences)
        )
        return int(result.scalar_one())


async def test_defaults_are_created_on_first_read(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    response = await api.get("/api/v1/preferences")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data == {
        "theme": "system",
        "default_top_k": 5,
        "require_approval_by_default": False,
        "notifications_enabled": True,
    }
    assert await _row_count(db) == 1


async def test_reads_do_not_create_extra_rows(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await api.get("/api/v1/preferences")
    await api.get("/api/v1/preferences")

    assert await _row_count(db) == 1


async def test_partial_update_persists_and_leaves_others_alone(
    api: AsyncClient,
) -> None:
    patched = await api.patch(
        "/api/v1/preferences", json={"theme": "dark", "default_top_k": 8}
    )

    assert patched.status_code == 200
    data = patched.json()["data"]
    assert data["theme"] == "dark"
    assert data["default_top_k"] == 8
    assert data["notifications_enabled"] is True  # untouched

    # Survives a fresh read (it is in the database, not in memory).
    reread = await api.get("/api/v1/preferences")
    assert reread.json()["data"]["theme"] == "dark"


async def test_validation_bounds(api: AsyncClient) -> None:
    bad_theme = await api.patch("/api/v1/preferences", json={"theme": "neon"})
    too_wide = await api.patch("/api/v1/preferences", json={"default_top_k": 99})

    assert bad_theme.status_code == 422
    assert too_wide.status_code == 422


class TestPreferencesAffectBehavior:
    """A preference nobody reads is decoration; these pin the wiring."""

    async def test_rag_query_uses_default_top_k_when_omitted(
        self, api: AsyncClient, app: FastAPI, db: SqlAlchemyDatabaseProvider
    ) -> None:
        from tests.fakes import FakeEmbeddingProvider, FakeVectorStore

        vectors = FakeVectorStore()
        app.state.embeddings = FakeEmbeddingProvider()
        app.state.vector_store = vectors
        await api.patch("/api/v1/preferences", json={"default_top_k": 9})

        response = await api.post("/api/v1/rag/query", json={"query": "anything"})

        assert response.status_code == 200, response.text
        assert vectors.last_top_k == 9

    async def test_explicit_top_k_still_wins(
        self, api: AsyncClient, app: FastAPI, db: SqlAlchemyDatabaseProvider
    ) -> None:
        from tests.fakes import FakeEmbeddingProvider, FakeVectorStore

        vectors = FakeVectorStore()
        app.state.embeddings = FakeEmbeddingProvider()
        app.state.vector_store = vectors
        await api.patch("/api/v1/preferences", json={"default_top_k": 9})

        response = await api.post(
            "/api/v1/rag/query", json={"query": "anything", "top_k": 2}
        )

        assert response.status_code == 200
        assert vectors.last_top_k == 2

    async def test_disabling_notifications_suppresses_dispatch(
        self, api: AsyncClient, db: SqlAlchemyDatabaseProvider
    ) -> None:
        from app.features.notifications.dispatcher import NotificationDispatcher
        from app.infrastructure.notifications.inapp import InAppNotificationProvider

        from tests.helpers import workspace_user_id

        user_id = await workspace_user_id(db)
        dispatcher = NotificationDispatcher(db, [InAppNotificationProvider(db)])

        await api.patch("/api/v1/preferences", json={"notifications_enabled": False})
        await dispatcher.dispatch(user_id, kind="test", title="t", body="b")
        assert (await api.get("/api/v1/notifications")).json()["data"] == []

        # Re-enabling restores delivery.
        await api.patch("/api/v1/preferences", json={"notifications_enabled": True})
        await dispatcher.dispatch(user_id, kind="test", title="t", body="b")
        assert len((await api.get("/api/v1/notifications")).json()["data"]) == 1
