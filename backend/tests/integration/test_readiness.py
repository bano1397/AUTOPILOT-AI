"""Integration test for the readiness endpoint."""

from __future__ import annotations

from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


async def test_readiness_ok(app: FastAPI, db: SqlAlchemyDatabaseProvider) -> None:
    # Point the app at the isolated test database.
    app.state.db = db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
