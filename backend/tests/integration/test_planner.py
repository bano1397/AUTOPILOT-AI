"""Integration tests for the planner agent."""

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

from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeSearchProvider,
    FakeVectorStore,
)

_ALICE = ("alice@example.com", "alicepass1")

_PLAN_JSON = (
    '[{"title": "Choose newsletter platform", "description": "Compare options.",'
    ' "priority": "high"},'
    ' {"title": "Draft first issue", "priority": "medium"}]'
)


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
    app.state.search = FakeSearchProvider()
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


async def test_plan_request_creates_persisted_tasks(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    # "plan ..." fast-routes deterministically; only the plan reply is scripted.
    fake_llm.replies = [_PLAN_JSON]

    response = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(token),
        json={"message": "plan the launch of our newsletter"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "planner"
    assert "created 2 task(s)" in data["answer"]
    assert "Choose newsletter platform" in data["answer"]

    tasks = await api.get("/api/v1/tasks", headers=_auth(token))
    body = tasks.json()
    assert body["meta"]["total"] == 2
    by_title = {task["title"]: task for task in body["data"]}
    assert by_title["Choose newsletter platform"]["priority"] == "high"
    assert by_title["Choose newsletter platform"]["source"] == "planner"
    assert by_title["Draft first issue"]["priority"] == "medium"


async def test_planner_run_is_audited(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = [_PLAN_JSON]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "plan a thing"}
    )
    assert response.status_code == 200

    async with db.session() as session:
        result = await session.execute(select(AiExecution))
        features = {row.feature for row in result.scalars().all()}
    # Fast-routed: no classifier call, only the planner's own LLM call.
    assert features == {"agent.planner"}


async def test_unparseable_plan_saves_nothing_and_is_honest(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["Sure! First do A, then do B, then celebrate."]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "plan my week"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "planner"
    assert "couldn't turn that into a structured task list" in data["answer"]
    assert "then celebrate" in data["answer"]  # raw suggestion is surfaced

    tasks = await api.get("/api/v1/tasks", headers=_auth(token))
    assert tasks.json()["meta"]["total"] == 0
