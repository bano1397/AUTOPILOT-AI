"""Tests for the system health/metadata endpoints and correlation middleware."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["version"]
    assert body["environment"]


async def test_health_sets_correlation_id_header(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


async def test_inbound_correlation_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "test-cid-123"})

    assert response.headers["X-Request-ID"] == "test-cid-123"


async def test_root_returns_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["docs"] == "/docs"
