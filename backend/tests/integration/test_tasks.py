"""Integration tests for the tasks API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from app.core.security import hash_password
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_ALICE = ("alice@example.com", "alicepass1")
_BOB = ("bob@example.com", "bobpass123")


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed_and_login(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    email: str = _ALICE[0],
    password: str = _ALICE[1],
) -> str:
    async with db.session() as session:
        session.add(User(email=email, password_hash=hash_password(password)))
        await session.commit()
    response = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(response.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create(
    api: AsyncClient, token: str, title: str, priority: str = "medium"
) -> dict[str, object]:
    response = await api.post(
        "/api/v1/tasks",
        headers=_auth(token),
        json={"title": title, "priority": priority},
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


async def test_create_and_list_tasks(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)
    await _create(api, token, "Write report", priority="high")

    response = await api.get("/api/v1/tasks", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    task = body["data"][0]
    assert task["title"] == "Write report"
    assert task["priority"] == "high"
    assert task["status"] == "todo"
    assert task["source"] == "manual"


async def test_status_filter(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    token = await _seed_and_login(api, db)
    first = await _create(api, token, "A")
    await _create(api, token, "B")

    patched = await api.patch(
        f"/api/v1/tasks/{first['id']}",
        headers=_auth(token),
        json={"status": "done"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "done"

    done = await api.get("/api/v1/tasks?status=done", headers=_auth(token))
    todo = await api.get("/api/v1/tasks?status=todo", headers=_auth(token))
    assert done.json()["meta"]["total"] == 1
    assert todo.json()["meta"]["total"] == 1
    assert done.json()["data"][0]["id"] == first["id"]


async def test_partial_update_keeps_other_fields(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)
    task = await _create(api, token, "Original", priority="urgent")

    patched = await api.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=_auth(token),
        json={"title": "Renamed"},
    )

    data = patched.json()["data"]
    assert data["title"] == "Renamed"
    assert data["priority"] == "urgent"  # unchanged


async def test_delete_task(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    token = await _seed_and_login(api, db)
    task = await _create(api, token, "Ephemeral")

    deleted = await api.delete(f"/api/v1/tasks/{task['id']}", headers=_auth(token))
    assert deleted.status_code == 200

    listing = await api.get("/api/v1/tasks", headers=_auth(token))
    assert listing.json()["meta"]["total"] == 0


async def test_tasks_are_owner_scoped(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    alice = await _seed_and_login(api, db)
    bob = await _seed_and_login(api, db, *_BOB)
    task = await _create(api, alice, "Alice's task")

    assert (await api.get("/api/v1/tasks", headers=_auth(bob))).json()["meta"][
        "total"
    ] == 0
    patched = await api.patch(
        f"/api/v1/tasks/{task['id']}", headers=_auth(bob), json={"status": "done"}
    )
    deleted = await api.delete(f"/api/v1/tasks/{task['id']}", headers=_auth(bob))
    assert patched.status_code == 404
    assert deleted.status_code == 404


async def test_validation_and_auth(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)

    empty_title = await api.post(
        "/api/v1/tasks", headers=_auth(token), json={"title": ""}
    )
    bad_priority = await api.post(
        "/api/v1/tasks", headers=_auth(token), json={"title": "x", "priority": "nope"}
    )
    anonymous = await api.get("/api/v1/tasks")
    missing = await api.patch(
        f"/api/v1/tasks/{uuid4()}", headers=_auth(token), json={"status": "done"}
    )

    assert empty_title.status_code == 422
    assert bad_priority.status_code == 422
    assert anonymous.status_code == 401
    assert missing.status_code == 404
