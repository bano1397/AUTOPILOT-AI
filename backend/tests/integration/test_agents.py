"""Integration tests for the supervisor graph and agents API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.features.users.models import User
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecution, AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore

_ALICE = ("alice@example.com", "alicepass1")


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


async def _seed_and_login(api: AsyncClient, db: SqlAlchemyDatabaseProvider) -> str:
    email, password = _ALICE
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


async def test_agents_endpoints_require_authentication(api: AsyncClient) -> None:
    listing = await api.get("/api/v1/agents")
    ask = await api.post("/api/v1/agents/ask", json={"message": "hi"})
    assert listing.status_code == 401
    assert ask.status_code == 401


async def test_list_agents_returns_registered_agents(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)

    response = await api.get("/api/v1/agents", headers=_auth(token))

    assert response.status_code == 200
    agents = {entry["name"]: entry["description"] for entry in response.json()["data"]}
    assert "knowledge" in agents
    assert "general" in agents
    assert agents["knowledge"]  # descriptions are populated


async def test_supervisor_routes_document_question_to_knowledge_agent(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    document_id = await _upload(
        api, token, "handbook.txt", "Employees receive twenty vacation days. " * 30
    )
    # Call 1 = supervisor classification, call 2 = grounded answer.
    fake_llm.replies = ["knowledge", "You get 20 days [1]."]

    response = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(token),
        json={"message": "how many vacation days do we get?"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "knowledge"
    assert data["answer"] == "You get 20 days [1]."
    assert data["grounded"] is True
    assert data["sources"][0]["document_id"] == document_id
    assert len(fake_llm.calls) == 2


async def test_supervisor_routes_small_talk_to_general_agent(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "Hello! How can I help you today?"]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "hey there!"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "general"
    assert data["answer"] == "Hello! How can I help you today?"
    assert data["grounded"] is False
    assert data["sources"] == []


async def test_unparseable_routing_reply_falls_back_to_knowledge(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    # Garbage classification; no documents indexed -> honest no-context answer.
    fake_llm.replies = ["I think maybe the docs one??"]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "what is our policy?"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "knowledge"
    assert data["grounded"] is False
    # The knowledge agent skipped the LLM (no context), so only the supervisor called it.
    assert len(fake_llm.calls) == 1


async def test_agent_run_is_fully_audited(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    await _upload(api, token, "handbook.txt", "Vacation policy details. " * 40)
    fake_llm.replies = ["knowledge", "Answer [1]."]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "vacation policy?"}
    )
    assert response.status_code == 200

    async with db.session() as session:
        result = await session.execute(select(AiExecution).order_by(AiExecution.created_at))
        rows = list(result.scalars().all())
    features = {row.feature for row in rows}
    assert features == {"agent.supervisor", "agent.knowledge"}
    assert all(row.user_id is not None for row in rows)
    by_feature = {row.feature: row for row in rows}
    assert by_feature["agent.supervisor"].agent_name == "supervisor"
    assert by_feature["agent.knowledge"].agent_name == "knowledge"


async def test_ask_validation_bounds(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)

    empty = await api.post("/api/v1/agents/ask", headers=_auth(token), json={"message": ""})
    assert empty.status_code == 422
