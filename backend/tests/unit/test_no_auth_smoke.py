"""Smoke test: authentication is disabled — protected endpoints are open."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_is_open(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200


async def test_owner_scoped_endpoint_open_without_token(client: AsyncClient) -> None:
    # /documents was owner-scoped behind a bearer token; with auth disabled it
    # must resolve the shared public user and return 200 (no Authorization sent).
    response = await client.get("/api/v1/documents?page=1&page_size=10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
