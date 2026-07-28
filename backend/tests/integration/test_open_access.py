"""The API is open: every endpoint works with no credentials of any kind.

This is the counterpart to the deleted `*_require_authentication` tests. It is
deliberately blunt: if authentication is ever reintroduced, this file fails
loudly rather than letting a half-migrated state pass (see
``docs/COMPLETION_PLAN.md`` §3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def api(app: FastAPI, db: SqlAlchemyDatabaseProvider) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_health_is_open(api: AsyncClient) -> None:
    assert (await api.get("/health")).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/users/me",
        "/api/v1/users",
        "/api/v1/documents?page=1&page_size=10",
        "/api/v1/conversations?page=1&page_size=10",
        "/api/v1/workflows/runs?page=1&page_size=10",
        "/api/v1/approvals?page=1&page_size=10",
        "/api/v1/notifications?page=1&page_size=10",
        "/api/v1/notifications/unread-count",
        "/api/v1/tasks?page=1&page_size=10",
        "/api/v1/agents",
        "/api/v1/analytics/overview?days=30",
        "/api/v1/scheduler/jobs",
    ],
)
async def test_endpoint_is_reachable_without_credentials(
    api: AsyncClient, path: str
) -> None:
    response = await api.get(path)

    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text}"
    assert response.json()["success"] is True


async def test_no_authentication_routes_exist(app: FastAPI) -> None:
    paths = {getattr(route, "path", "") for route in app.routes}
    for gone in (
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
    ):
        assert gone not in paths, f"{gone} should have been removed"
