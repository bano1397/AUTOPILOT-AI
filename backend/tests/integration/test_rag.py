"""Integration tests for the RAG query API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_vectors() -> FakeVectorStore:
    return FakeVectorStore()


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_embeddings: FakeEmbeddingProvider,
    fake_vectors: FakeVectorStore,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = fake_embeddings
    app.state.vector_store = fake_vectors
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _upload(api: AsyncClient, name: str, text: str) -> str:
    response = await api.post(
        "/api/v1/documents",
        files={"file": (name, text.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


async def test_query_returns_cited_matches(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    document_id = await _upload(
        api, "handbook.txt", "Employees receive twenty vacation days per year. " * 30
    )

    response = await api.post(
        "/api/v1/rag/query",
        json={"query": "how many vacation days do employees get?", "top_k": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["query"] == "how many vacation days do employees get?"
    assert 1 <= len(data["matches"]) <= 3
    for match in data["matches"]:
        assert match["document_id"] == document_id
        assert match["filename"] == "handbook.txt"
        assert "vacation days" in match["text"]
        assert isinstance(match["chunk_index"], int)
        assert isinstance(match["distance"], float)


async def test_query_with_empty_index_returns_no_matches(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    response = await api.post(
        "/api/v1/rag/query", json={"query": "anything at all"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["matches"] == []


async def test_query_validation_bounds(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    empty = await api.post("/api/v1/rag/query", json={"query": ""})
    too_many = await api.post(
        "/api/v1/rag/query", json={"query": "q", "top_k": 21}
    )

    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_many.status_code == 422


async def test_embedding_outage_returns_502(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    fake_embeddings.fail = True

    response = await api.post(
        "/api/v1/rag/query", json={"query": "anything"}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_SERVICE_ERROR"
    assert "Embedding provider" in body["error"]["message"]