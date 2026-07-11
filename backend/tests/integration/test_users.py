"""Integration tests for the users API and RBAC."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from app.core.security import hash_password
from app.features.users.models import User, UserRole
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_ADMIN = ("admin@example.com", "adminpass1")
_USER = ("user@example.com", "userpass12")


@pytest_asyncio.fixture
async def api(app: FastAPI, db: SqlAlchemyDatabaseProvider) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed(
    db: SqlAlchemyDatabaseProvider,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> None:
    async with db.session() as session:
        session.add(
            User(email=email, password_hash=hash_password(password), role=role)
        )
        await session.commit()


async def _token(api: AsyncClient, email: str, password: str) -> str:
    response = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return str(response.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_requires_authentication(api: AsyncClient) -> None:
    response = await api.get("/api/v1/users")
    assert response.status_code == 401


async def test_normal_user_is_forbidden(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db, *_USER, role=UserRole.USER)
    token = await _token(api, *_USER)

    response = await api.get("/api/v1/users", headers=_auth(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_admin_can_list_users(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db, *_ADMIN, role=UserRole.ADMIN)
    token = await _token(api, *_ADMIN)

    response = await api.get("/api/v1/users", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["meta"]["total"] == 1
    assert body["data"][0]["email"] == _ADMIN[0]


async def test_admin_can_get_user_by_id(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db, *_ADMIN, role=UserRole.ADMIN)
    token = await _token(api, *_ADMIN)
    listed = await api.get("/api/v1/users", headers=_auth(token))
    user_id = listed.json()["data"][0]["id"]

    response = await api.get(f"/api/v1/users/{user_id}", headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["data"]["id"] == user_id


async def test_get_missing_user_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db, *_ADMIN, role=UserRole.ADMIN)
    token = await _token(api, *_ADMIN)

    response = await api.get(f"/api/v1/users/{uuid4()}", headers=_auth(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_pagination(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> None:
    await _seed(db, *_ADMIN, role=UserRole.ADMIN)
    for index in range(4):
        await _seed(db, f"extra{index}@example.com", "password12")
    token = await _token(api, *_ADMIN)

    response = await api.get(
        "/api/v1/users", params={"page": 1, "page_size": 2}, headers=_auth(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5  # 1 admin + 4 extra
    assert body["meta"]["page_size"] == 2
    assert body["meta"]["pages"] == 3
