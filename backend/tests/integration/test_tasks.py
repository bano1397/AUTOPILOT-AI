"""Integration tests for the tasks API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _create(
    api: AsyncClient, title: str, priority: str = "medium"
) -> dict[str, object]:
    response = await api.post(
        "/api/v1/tasks",
        json={"title": title, "priority": priority},
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


async def test_create_and_list_tasks(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _create(api, "Write report", priority="high")

    response = await api.get("/api/v1/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    task = body["data"][0]
    assert task["title"] == "Write report"
    assert task["priority"] == "high"
    assert task["status"] == "todo"
    assert task["source"] == "manual"


async def test_status_filter(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    first = await _create(api, "A")
    await _create(api, "B")

    patched = await api.patch(
        f"/api/v1/tasks/{first['id']}",
        json={"status": "done"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "done"

    done = await api.get("/api/v1/tasks?status=done")
    todo = await api.get("/api/v1/tasks?status=todo")
    assert done.json()["meta"]["total"] == 1
    assert todo.json()["meta"]["total"] == 1
    assert done.json()["data"][0]["id"] == first["id"]


async def test_partial_update_keeps_other_fields(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    task = await _create(api, "Original", priority="urgent")

    patched = await api.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Renamed"},
    )

    data = patched.json()["data"]
    assert data["title"] == "Renamed"
    assert data["priority"] == "urgent"  # unchanged


async def test_delete_task(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    task = await _create(api, "Ephemeral")

    deleted = await api.delete(f"/api/v1/tasks/{task['id']}")
    assert deleted.status_code == 200

    listing = await api.get("/api/v1/tasks")
    assert listing.json()["meta"]["total"] == 0


async def test_validation(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    empty_title = await api.post(
        "/api/v1/tasks", json={"title": ""}
    )
    bad_priority = await api.post(
        "/api/v1/tasks", json={"title": "x", "priority": "nope"}
    )
    missing = await api.patch(
        f"/api/v1/tasks/{uuid4()}", json={"status": "done"}
    )

    assert empty_title.status_code == 422
    assert bad_priority.status_code == 422
    assert missing.status_code == 404
