"""Integration tests for the workspace identity and users listing.

There is no authentication and no role model (``docs/COMPLETION_PLAN.md`` §3),
so these tests cover identity provisioning and the listing's pagination math
rather than access control.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from app.features.users.dependencies import WORKSPACE_USER_EMAIL
from app.features.users.models import User
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


async def _seed(db: SqlAlchemyDatabaseProvider, email: str) -> None:
    async with db.session() as session:
        session.add(User(email=email))
        await session.commit()


async def _user_count(db: SqlAlchemyDatabaseProvider) -> int:
    async with db.session() as session:
        result = await session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())


async def test_me_returns_the_workspace_identity(api: AsyncClient) -> None:
    response = await api.get("/api/v1/users/me")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == WORKSPACE_USER_EMAIL
    assert body["data"]["is_active"] is True
    # No auth means there is no password hash and no role to leak.
    assert "password_hash" not in body["data"]
    assert "role" not in body["data"]


async def test_workspace_identity_is_provisioned_once(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    first = await api.get("/api/v1/users/me")
    second = await api.get("/api/v1/users/me")

    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert await _user_count(db) == 1


async def test_me_is_reachable_without_any_credentials(api: AsyncClient) -> None:
    # No Authorization header, no cookie — the request must still succeed.
    assert api.headers.get("Authorization") is None
    assert (await api.get("/api/v1/users/me")).status_code == 200


async def test_list_users_is_open(api: AsyncClient) -> None:
    await api.get("/api/v1/users/me")  # provision the identity

    response = await api.get("/api/v1/users")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["email"] == WORKSPACE_USER_EMAIL


async def test_get_user_by_id(api: AsyncClient) -> None:
    me = await api.get("/api/v1/users/me")
    user_id = me.json()["data"]["id"]

    response = await api.get(f"/api/v1/users/{user_id}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == user_id


async def test_get_missing_user_returns_404(api: AsyncClient) -> None:
    response = await api.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_pagination(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    await api.get("/api/v1/users/me")  # the workspace identity is row 1
    for index in range(4):
        await _seed(db, f"extra{index}@example.com")

    response = await api.get("/api/v1/users", params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5  # workspace identity + 4 seeded
    assert body["meta"]["page_size"] == 2
    assert body["meta"]["pages"] == 3
