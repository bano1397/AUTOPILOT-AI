"""Integration tests for the grounded ask API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecution, AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(reply="Employees get 20 vacation days [1].")


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_llm: FakeLLMProvider,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.llm = fake_llm
    # The recorder must write to the test database, not the production one.
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
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


async def test_ask_returns_grounded_answer_with_sources(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    document_id = await _upload(
        api, "handbook.txt", "Employees receive twenty vacation days per year. " * 30
    )

    response = await api.post(
        "/api/v1/rag/ask",
        json={"query": "how many vacation days do employees get?", "top_k": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer"] == "Employees get 20 vacation days [1]."
    assert data["grounded"] is True
    assert data["model"] == "fake-llm"
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["document_id"] == document_id
    assert data["sources"][0]["filename"] == "handbook.txt"

    # The grounded prompt actually carried the context and the question.
    (conversation,) = fake_llm.calls
    system, user_message = conversation
    assert "ONLY" in system.content
    assert "handbook.txt" in user_message.content
    assert "vacation days" in user_message.content
    assert "how many vacation days do employees get?" in user_message.content


async def test_ask_is_recorded_in_ai_executions(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _upload(api, "handbook.txt", "Vacation policy details. " * 40)

    response = await api.post(
        "/api/v1/rag/ask", json={"query": "vacation policy?"}
    )
    assert response.status_code == 200

    async with db.session() as session:
        result = await session.execute(select(AiExecution))
        rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].feature == "rag.ask"
    assert rows[0].user_id is not None
    assert rows[0].model == "fake-llm"
    assert rows[0].error is None


async def test_ask_without_context_skips_llm(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:

    response = await api.post(
        "/api/v1/rag/ask", json={"query": "anything at all"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["grounded"] is False
    assert data["model"] is None
    assert data["sources"] == []
    assert "couldn't find anything relevant" in data["answer"]
    assert fake_llm.calls == []  # the LLM was never invoked


async def test_ask_llm_outage_returns_502_and_is_recorded(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    await _upload(api, "handbook.txt", "Vacation policy details. " * 40)
    fake_llm.fail = True

    response = await api.post(
        "/api/v1/rag/ask", json={"query": "vacation policy?"}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_SERVICE_ERROR"
    assert "LLM provider" in body["error"]["message"]

    # The failed call is still audited.
    async with db.session() as session:
        result = await session.execute(select(AiExecution))
        rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].error == "llm service unavailable"


async def test_ask_validation_bounds(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    empty = await api.post("/api/v1/rag/ask", json={"query": ""})
    too_many = await api.post(
        "/api/v1/rag/ask", json={"query": "q", "top_k": 21}
    )

    assert empty.status_code == 422
    assert too_many.status_code == 422
