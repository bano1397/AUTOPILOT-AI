"""Integration tests for security headers.

The auth-cookie and login rate-limit cases that used to live here were removed
with authentication itself (``docs/COMPLETION_PLAN.md`` §3). Response headers are
the security hardening that remains.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

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


async def test_no_session_cookie_is_ever_set(api: AsyncClient) -> None:
    # Nothing authenticates, so no endpoint should hand out a cookie.
    for path in ("/health", "/api/v1/users/me", "/api/v1/agents"):
        response = await api.get(path)
        assert "set-cookie" not in response.headers, path
