"""Integration tests for the RAG query API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore

_ALICE = ("alice@example.com", "alicepass1")
_BOB = ("bob@example.com", "bobpass123")


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


async def _seed_and_login(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, email: str, password: str
) -> str:
    async with db.session() as session:
        session.add(User(email=email, password_hash=hash_password(password)))
        await session.commit()
    response = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(response.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(api: AsyncClient, token: str, name: str, text: str) -> str:
    response = await api.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": (name, text.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


async def test_query_requires_authentication(api: AsyncClient) -> None:
    response = await api.post("/api/v1/rag/query", json={"query": "anything"})
    assert response.status_code == 401


async def test_query_returns_cited_matches(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ALICE)
    document_id = await _upload(
        api, token, "handbook.txt", "Employees receive twenty vacation days per year. " * 30
    )

    response = await api.post(
        "/api/v1/rag/query",
        headers=_auth(token),
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


async def test_query_is_owner_isolated(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    alice = await _seed_and_login(api, db, *_ALICE)
    bob = await _seed_and_login(api, db, *_BOB)
    await _upload(api, alice, "alice-secrets.txt", "Alice's confidential notes. " * 30)

    response = await api.post(
        "/api/v1/rag/query", headers=_auth(bob), json={"query": "confidential notes"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["matches"] == []


async def test_query_with_empty_index_returns_no_matches(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ALICE)

    response = await api.post(
        "/api/v1/rag/query", headers=_auth(token), json={"query": "anything at all"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["matches"] == []


async def test_query_validation_bounds(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db, *_ALICE)

    empty = await api.post("/api/v1/rag/query", headers=_auth(token), json={"query": ""})
    too_many = await api.post(
        "/api/v1/rag/query", headers=_auth(token), json={"query": "q", "top_k": 21}
    )

    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_many.status_code == 422


async def test_embedding_outage_returns_502(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    token = await _seed_and_login(api, db, *_ALICE)
    fake_embeddings.fail = True

    response = await api.post(
        "/api/v1/rag/query", headers=_auth(token), json={"query": "anything"}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_SERVICE_ERROR"
    assert "Embedding provider" in body["error"]["message"]