"""Integration tests for the prompts introspection API."""

from __future__ import annotations

from collections.abc import AsyncIterator

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


async def test_listing_returns_every_catalogued_prompt(api: AsyncClient) -> None:
    response = await api.get("/api/v1/prompts")

    assert response.status_code == 200, response.text
    # The listing carries every version, so pick the active one rather than
    # keying by prompt name: routing is on v2 since the calendar agent landed.
    rows = response.json()["data"]
    routing = next(
        row
        for row in rows
        if row["key"] == "agent.supervisor.routing" and row["active"]
    )
    assert routing["version"] == 2
    assert "EXACTLY one" in routing["body"]
    assert "calendar:" in routing["body"]


async def test_versions_for_one_key(api: AsyncClient) -> None:
    response = await api.get("/api/v1/prompts/rag.ask.system")

    assert response.status_code == 200
    versions = response.json()["data"]
    assert [v["version"] for v in versions] == [1]


async def test_unknown_key_returns_404(api: AsyncClient) -> None:
    response = await api.get("/api/v1/prompts/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_versions_accumulate_for_a_revised_prompt(api: AsyncClient) -> None:
    """agent.general.system gained v2 (memory-aware); v1 is retained."""
    response = await api.get("/api/v1/prompts/agent.general.system")

    assert response.status_code == 200
    versions = {v["version"]: v for v in response.json()["data"]}
    assert sorted(versions) == [1, 2]
    assert versions[1]["active"] is False
    assert versions[2]["active"] is True


async def test_render_preview(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render",
        json={"variables": {"memories": []}},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == 2
    assert data["rendered"].startswith("You are AutoPilot AI")


async def test_render_preview_of_a_superseded_version(api: AsyncClient) -> None:
    """A retired version stays renderable — that is what reproducibility means."""
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render",
        json={"variables": {}, "version": 1},
    )

    assert response.status_code == 200
    assert response.json()["data"]["version"] == 1


async def test_render_missing_declared_variable_is_rejected(api: AsyncClient) -> None:
    """StrictUndefined is the point: a prompt with a hole must not render."""
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render", json={"variables": {}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROMPT_ERROR"


async def test_render_unknown_version_returns_404(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render",
        json={"variables": {}, "version": 7},
    )

    assert response.status_code == 404
