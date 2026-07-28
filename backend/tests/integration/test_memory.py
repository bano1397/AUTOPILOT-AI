"""Integration tests for long-term memory (blueprint §16, level 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore
from tests.helpers import workspace_user_id


@pytest_asyncio.fixture
async def memory_vectors(app: FastAPI) -> FakeVectorStore:
    """Bind fake embedding + memory vector providers to the app."""
    vectors = FakeVectorStore()
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.memory_vector_store = vectors
    return vectors


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, memory_vectors: FakeVectorStore
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_remember_persists_and_indexes(
    api: AsyncClient, memory_vectors: FakeVectorStore
) -> None:
    response = await api.post(
        "/api/v1/memory",
        json={"content": "The fiscal year starts in April.", "source": "onboarding"},
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["content"] == "The fiscal year starts in April."
    assert data["kind"] == "fact"
    assert data["source"] == "onboarding"
    assert data["indexed"] is True

    # The vector id is the row id, so the two stores stay joinable.
    assert data["vector_id"] == data["id"]
    assert list(memory_vectors.vectors) == [data["id"]]


async def test_recall_returns_stored_facts_with_relevance(api: AsyncClient) -> None:
    await api.post("/api/v1/memory", json={"content": "Invoices are net 30."})

    response = await api.post("/api/v1/memory/recall", json={"query": "invoices"})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["entry"]["content"] == "Invoices are net 30."
    assert 0.0 <= data[0]["relevance"] <= 1.0


async def test_recall_uses_default_top_k_when_omitted(
    api: AsyncClient, memory_vectors: FakeVectorStore
) -> None:
    await api.patch("/api/v1/preferences", json={"default_top_k": 7})

    await api.post("/api/v1/memory/recall", json={"query": "anything"})

    assert memory_vectors.last_top_k == 7


async def test_explicit_top_k_still_wins(
    api: AsyncClient, memory_vectors: FakeVectorStore
) -> None:
    await api.patch("/api/v1/preferences", json={"default_top_k": 7})

    await api.post("/api/v1/memory/recall", json={"query": "anything", "top_k": 2})

    assert memory_vectors.last_top_k == 2


async def test_list_is_paginated_newest_first(api: AsyncClient) -> None:
    for index in range(3):
        await api.post("/api/v1/memory", json={"content": f"fact {index}"})

    response = await api.get("/api/v1/memory", params={"page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3


async def test_list_filters_by_kind(api: AsyncClient) -> None:
    await api.post("/api/v1/memory", json={"content": "a fact"})
    await api.post(
        "/api/v1/memory", json={"content": "likes brevity", "kind": "preference"}
    )

    response = await api.get("/api/v1/memory", params={"kind": "preference"})

    data = response.json()["data"]
    assert [item["content"] for item in data] == ["likes brevity"]


async def test_forget_removes_row_and_vector(
    api: AsyncClient, memory_vectors: FakeVectorStore
) -> None:
    created = await api.post("/api/v1/memory", json={"content": "temporary"})
    entry_id = created.json()["data"]["id"]

    deleted = await api.delete(f"/api/v1/memory/{entry_id}")

    assert deleted.status_code == 200
    assert memory_vectors.vectors == {}
    assert (await api.get("/api/v1/memory")).json()["data"] == []


async def test_forgetting_an_unknown_entry_is_404(api: AsyncClient) -> None:
    response = await api.delete("/api/v1/memory/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


async def test_validation_rejects_empty_content(api: AsyncClient) -> None:
    response = await api.post("/api/v1/memory", json={"content": ""})

    assert response.status_code == 422


class TestDegradation:
    """Storage must not be lost just because indexing failed."""

    async def test_remember_survives_embedding_failure_and_says_so(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        app.state.embeddings = FakeEmbeddingProvider(fail=True)

        response = await api.post("/api/v1/memory", json={"content": "still kept"})

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["vector_id"] is None
        assert data["indexed"] is False, "an unindexed entry must not claim otherwise"

        # It is listable, just not recallable.
        listed = (await api.get("/api/v1/memory")).json()["data"]
        assert [item["content"] for item in listed] == ["still kept"]

    async def test_recall_reports_an_outage_rather_than_empty_results(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Silently returning [] would read as 'nothing stored'."""
        app.state.embeddings = FakeEmbeddingProvider(fail=True)

        response = await api.post("/api/v1/memory/recall", json={"query": "anything"})

        assert response.status_code == 502, response.text


class TestNamespaceIsolation:
    """Memory vectors must never surface as document search results."""

    async def test_memory_does_not_leak_into_rag_query(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        document_vectors = FakeVectorStore()
        app.state.vector_store = document_vectors

        await api.post("/api/v1/memory", json={"content": "a durable fact"})

        response = await api.post("/api/v1/rag/query", json={"query": "fact"})

        assert response.status_code == 200, response.text
        assert response.json()["data"]["matches"] == []
        assert document_vectors.vectors == {}, "memory wrote into the document store"


class TestMemoryReachesTheAgent:
    """A memory nobody recalls is decoration; these pin the wiring."""

    async def test_general_agent_prompt_carries_recalled_facts(
        self, api: AsyncClient, app: FastAPI, db: SqlAlchemyDatabaseProvider
    ) -> None:
        from app.platform.observability import AiExecutionRecorder

        fake_llm = FakeLLMProvider(replies=["general", "Sure thing."])
        app.state.llm = fake_llm
        app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)

        await api.post(
            "/api/v1/memory", json={"content": "The fiscal year starts in April."}
        )

        response = await api.post("/api/v1/agents/ask", json={"message": "hi"})

        assert response.status_code == 200, response.text
        assert response.json()["data"]["agent"] == "general"

        # Call 1 = supervisor routing, call 2 = the general agent.
        system_message = fake_llm.calls[1][0].content
        assert "The fiscal year starts in April." in system_message

    async def test_prompt_is_unchanged_when_nothing_is_remembered(
        self, api: AsyncClient, app: FastAPI, db: SqlAlchemyDatabaseProvider
    ) -> None:
        from app.platform.observability import AiExecutionRecorder
        from app.platform.prompts.registry import prompt_registry

        fake_llm = FakeLLMProvider(replies=["general", "Sure thing."])
        app.state.llm = fake_llm
        app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)

        await api.post("/api/v1/agents/ask", json={"message": "hi"})

        system_message = fake_llm.calls[1][0].content
        assert system_message == prompt_registry.get("agent.general.system", 1).body

    async def test_agent_still_answers_when_recall_fails(
        self, api: AsyncClient, app: FastAPI, db: SqlAlchemyDatabaseProvider
    ) -> None:
        """Memory is an enhancement; an outage must not cost the reply."""
        from app.platform.observability import AiExecutionRecorder

        fake_llm = FakeLLMProvider(replies=["general", "Still here."])
        app.state.llm = fake_llm
        app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
        app.state.embeddings = FakeEmbeddingProvider(fail=True)

        response = await api.post("/api/v1/agents/ask", json={"message": "hi"})

        assert response.status_code == 200, response.text
        assert response.json()["data"]["answer"] == "Still here."


class TestOrphanVectors:
    """A vector whose row is gone must not resurrect a forgotten fact."""

    async def test_recall_skips_vectors_with_no_surviving_row(
        self,
        api: AsyncClient,
        db: SqlAlchemyDatabaseProvider,
        memory_vectors: FakeVectorStore,
    ) -> None:
        created = await api.post("/api/v1/memory", json={"content": "forgotten"})
        entry_id = created.json()["data"]["id"]
        user_id = await workspace_user_id(db)

        # Simulate a failed vector delete: drop the row, keep the vector. The
        # metadata must still match the owner filter, or this would pass for
        # the wrong reason.
        await api.delete(f"/api/v1/memory/{entry_id}")
        memory_vectors.vectors[entry_id] = {
            "embedding": [1.0, 1.0, 0.0],
            "document": "forgotten",
            "metadata": {"user_id": str(user_id), "kind": "fact", "source": ""},
        }

        response = await api.post("/api/v1/memory/recall", json={"query": "forgotten"})

        assert response.status_code == 200
        assert response.json()["data"] == []
