"""Integration tests for conversation memory and the conversations API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore

_ALICE = ("alice@example.com", "alicepass1")
_BOB = ("bob@example.com", "bobpass123")


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


async def _seed_and_login(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    email: str = _ALICE[0],
    password: str = _ALICE[1],
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


async def _ask(
    api: AsyncClient, token: str, message: str, conversation_id: str | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = await api.post("/api/v1/agents/ask", headers=_auth(token), json=body)
    assert response.status_code == 200
    return dict(response.json()["data"])


async def test_ask_creates_conversation_and_persists_exchange(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "Hello Alice!"]

    data = await _ask(api, token, "hello there")
    conversation_id = str(data["conversation_id"])
    assert conversation_id

    detail = await api.get(
        f"/api/v1/conversations/{conversation_id}", headers=_auth(token)
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
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "The capital of France is Paris."]
    first = await _ask(api, token, "what is the capital of France?")
    conversation_id = str(first["conversation_id"])

    fake_llm.replies = ["general", "It has about 2.1 million residents."]
    second = await _ask(api, token, "and how many people live there?", conversation_id)

    assert str(second["conversation_id"]) == conversation_id
    # 4 LLM calls total: (supervisor, answer) x 2 turns.
    assert len(fake_llm.calls) == 4
    # The second answer prompt (last call) must contain the prior exchange.
    final_prompt = fake_llm.calls[-1]
    prompt_text = "\n".join(message.content for message in final_prompt)
    assert "what is the capital of France?" in prompt_text
    assert "The capital of France is Paris." in prompt_text

    detail = await api.get(
        f"/api/v1/conversations/{conversation_id}", headers=_auth(token)
    )
    messages = detail.json()["data"]["messages"]
    assert [message["position"] for message in messages] == [0, 1, 2, 3]


async def test_conversations_are_listed_for_owner(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "a", "general", "b"]
    first = await _ask(api, token, "first conversation")
    second = await _ask(api, token, "second conversation")

    response = await api.get("/api/v1/conversations", headers=_auth(token))

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


async def test_conversation_access_is_owner_scoped(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    alice = await _seed_and_login(api, db)
    bob = await _seed_and_login(api, db, *_BOB)
    fake_llm.replies = ["general", "hi"]
    data = await _ask(api, alice, "alice's private chat")
    conversation_id = str(data["conversation_id"])

    # Bob cannot read it...
    read = await api.get(f"/api/v1/conversations/{conversation_id}", headers=_auth(bob))
    assert read.status_code == 404
    # ...and cannot continue it.
    fake_llm.replies = ["general", "nope"]
    hijack = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(bob),
        json={"message": "continuing", "conversation_id": conversation_id},
    )
    assert hijack.status_code == 404


async def test_unknown_conversation_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)

    response = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(token),
        json={"message": "hi", "conversation_id": str(uuid4())},
    )

    assert response.status_code == 404


async def test_conversations_require_authentication(api: AsyncClient) -> None:
    listing = await api.get("/api/v1/conversations")
    detail = await api.get(f"/api/v1/conversations/{uuid4()}")
    assert listing.status_code == 401
    assert detail.status_code == 401
