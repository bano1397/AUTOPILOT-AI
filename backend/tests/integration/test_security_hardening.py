"""Integration tests for security hardening: headers, rate limits, auth cookie."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.core.config import get_settings
from app.core.security import hash_password
from app.features.auth.router import REFRESH_COOKIE
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch

_ALICE = ("alice@example.com", "alicepass1")


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed(db: SqlAlchemyDatabaseProvider) -> None:
    async with db.session() as session:
        session.add(
            User(email=_ALICE[0], password_hash=hash_password(_ALICE[1]))
        )
        await session.commit()


async def _login(api: AsyncClient) -> dict[str, str]:
    response = await api.post(
        "/api/v1/auth/login", json={"email": _ALICE[0], "password": _ALICE[1]}
    )
    assert response.status_code == 200
    return dict(response.json()["data"])


async def test_security_headers_are_present(api: AsyncClient) -> None:
    response = await api.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    # No HSTS outside production.
    assert "Strict-Transport-Security" not in response.headers


async def test_docs_page_is_exempt_from_api_csp(api: AsyncClient) -> None:
    response = await api.get("/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


async def test_login_rate_limit_returns_429(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, monkeypatch: MonkeyPatch
) -> None:
    await _seed(db)
    monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)

    for _ in range(3):
        ok = await api.post(
            "/api/v1/auth/login", json={"email": _ALICE[0], "password": _ALICE[1]}
        )
        assert ok.status_code == 200

    blocked = await api.post(
        "/api/v1/auth/login", json={"email": _ALICE[0], "password": _ALICE[1]}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


async def test_login_sets_httponly_refresh_cookie(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db)

    response = await api.post(
        "/api/v1/auth/login", json={"email": _ALICE[0], "password": _ALICE[1]}
    )

    set_cookie = response.headers["set-cookie"]
    assert REFRESH_COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


async def test_refresh_works_from_cookie_alone(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db)
    await _login(api)  # httpx keeps the cookie on the client

    # Empty body: the token must come from the cookie.
    response = await api.post("/api/v1/auth/refresh", json={})

    assert response.status_code == 200
    assert response.json()["data"]["access_token"]
    # Rotation: a fresh cookie was set on the response.
    assert REFRESH_COOKIE in response.headers.get("set-cookie", "")


async def test_refresh_without_cookie_or_body_is_401(api: AsyncClient) -> None:
    response = await api.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 401


async def test_logout_clears_cookie_and_revokes(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _seed(db)
    tokens = await _login(api)

    logout = await api.post("/api/v1/auth/logout", json={})
    assert logout.status_code == 200
    # The cookie is cleared on the client...
    assert REFRESH_COOKIE not in api.cookies

    # ...and the revoked token is dead even if presented via body.
    replay = await api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401
