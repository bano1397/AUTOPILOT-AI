"""Integration tests for the authentication API."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_EMAIL = "user@example.com"
_PASSWORD = "supersecret1"


@pytest_asyncio.fixture
async def api(app: FastAPI, db: SqlAlchemyDatabaseProvider) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the app with the isolated test database."""
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _register(api: AsyncClient, email: str = _EMAIL, password: str = _PASSWORD) -> None:
    response = await api.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201


async def _login(api: AsyncClient) -> dict[str, str]:
    response = await api.post(
        "/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["data"]


async def test_register_returns_user_envelope(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == _EMAIL
    assert body["data"]["role"] == "user"


async def test_register_duplicate_returns_conflict(api: AsyncClient) -> None:
    await _register(api)
    response = await api.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"


async def test_register_rejects_short_password(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": "short"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_returns_token_pair(api: AsyncClient) -> None:
    await _register(api)
    data = await _login(api)

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


async def test_login_wrong_password_unauthorized(api: AsyncClient) -> None:
    await _register(api)
    response = await api.post(
        "/api/v1/auth/login", json={"email": _EMAIL, "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


async def test_me_requires_authentication(api: AsyncClient) -> None:
    response = await api.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)

    response = await api.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["email"] == _EMAIL


async def test_refresh_rotates_and_invalidates_old_token(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)
    old_refresh = tokens["refresh_token"]

    first = await api.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_refresh = first.json()["data"]["refresh_token"]
    assert new_refresh != old_refresh

    # The rotated (old) token must no longer be accepted.
    replay = await api.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_logout_revokes_refresh_token(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)

    logout = await api.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 200

    after = await api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert after.status_code == 401
