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
    prompts = {prompt["key"]: prompt for prompt in response.json()["data"]}
    assert "agent.supervisor.routing" in prompts
    routing = prompts["agent.supervisor.routing"]
    assert routing["version"] == 1
    assert routing["active"] is True
    assert "EXACTLY one" in routing["body"]


async def test_versions_for_one_key(api: AsyncClient) -> None:
    response = await api.get("/api/v1/prompts/rag.ask.system")

    assert response.status_code == 200
    versions = response.json()["data"]
    assert [v["version"] for v in versions] == [1]


async def test_unknown_key_returns_404(api: AsyncClient) -> None:
    response = await api.get("/api/v1/prompts/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_render_preview(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render", json={"variables": {}}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == 1
    assert data["rendered"].startswith("You are AutoPilot AI")


async def test_render_unknown_version_returns_404(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/prompts/agent.general.system/render",
        json={"variables": {}, "version": 7},
    )

    assert response.status_code == 404
