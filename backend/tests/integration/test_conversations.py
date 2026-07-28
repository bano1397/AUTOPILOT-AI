"""Integration tests for conversation memory and the conversations API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


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
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _ask(
    api: AsyncClient, message: str, conversation_id: str | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = await api.post("/api/v1/agents/ask", json=body)
    assert response.status_code == 200
    return dict(response.json()["data"])


async def test_ask_creates_conversation_and_persists_exchange(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = ["general", "Hello Alice!"]

    data = await _ask(api, "hello there")
    conversation_id = str(data["conversation_id"])
    assert conversation_id

    detail = await api.get(
        f"/api/v1/conversations/{conversation_id}"
    )
    assert detail.status_code == 200
    payload = detail.json()["data"]
    assert payload["conversation"]["title"] == "hello there"
    roles = [message["role"] for message in payload["messages"]]
    contents = [message["content"] for message in payload["messages"]]
    assert roles == ["user", "assistant"]
    assert contents == ["hello there", "Hello Alice!"]
    assert payload["messages"][1]["meta"]["agent"] == "general"


async def test_follow_up_reuses_thread_and_feeds_history_to_llm(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = ["general", "The capital of France is Paris."]
    first = await _ask(api, "what is the capital of France?")
    conversation_id = str(first["conversation_id"])

    fake_llm.replies = ["general", "It has about 2.1 million residents."]
    second = await _ask(api, "and how many people live there?", conversation_id)

    assert str(second["conversation_id"]) == conversation_id
    # 4 LLM calls total: (supervisor, answer) x 2 turns.
    assert len(fake_llm.calls) == 4
    # The second answer prompt (last call) must contain the prior exchange.
    final_prompt = fake_llm.calls[-1]
    prompt_text = "\n".join(message.content for message in final_prompt)
    assert "what is the capital of France?" in prompt_text
    assert "The capital of France is Paris." in prompt_text

    detail = await api.get(
        f"/api/v1/conversations/{conversation_id}"
    )
    messages = detail.json()["data"]["messages"]
    assert [message["position"] for message in messages] == [0, 1, 2, 3]


async def test_conversations_are_listed_for_owner(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = ["general", "a", "general", "b"]
    first = await _ask(api, "first conversation")
    second = await _ask(api, "second conversation")

    response = await api.get("/api/v1/conversations")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    listed_ids = {entry["id"] for entry in body["data"]}
    # Ordering is updated_at DESC, but SQLite timestamps are second-granular,
    # so same-second creations tie — assert membership, not order.
    assert listed_ids == {
        str(first["conversation_id"]),
        str(second["conversation_id"]),
    }


async def test_unknown_conversation_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    response = await api.post(
        "/api/v1/agents/ask",
        json={"message": "hi", "conversation_id": str(uuid4())},
    )

    assert response.status_code == 404

