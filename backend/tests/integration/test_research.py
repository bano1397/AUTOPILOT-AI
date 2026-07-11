"""Integration tests for the research agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.domain.interfaces.search import SearchResult
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

_RESULTS = [
    SearchResult(
        title="LangGraph 1.2 released",
        url="https://example.com/langgraph-1-2",
        snippet="LangGraph 1.2 ships durable checkpoints.",
    ),
    SearchResult(
        title="LangGraph docs",
        url="https://example.com/docs",
        snippet="Official documentation.",
    ),
]


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def fake_search() -> FakeSearchProvider:
    return FakeSearchProvider(
        results=list(_RESULTS),
        pages={
            "https://example.com/langgraph-1-2": (
                "LangGraph 1.2 introduces durable execution and checkpoints."
            )
            # docs page intentionally missing: fetch fails -> snippet fallback
        },
    )


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_llm: FakeLLMProvider,
    fake_search: FakeSearchProvider,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.llm = fake_llm
    app.state.search = fake_search
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


async def test_research_question_routes_and_cites_web_sources(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_llm: FakeLLMProvider,
    fake_search: FakeSearchProvider,
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["research", "LangGraph 1.2 adds durable checkpoints [1]."]

    response = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(token),
        json={"message": "what is the latest LangGraph release?"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "research"
    assert data["answer"] == "LangGraph 1.2 adds durable checkpoints [1]."
    assert data["grounded"] is False
    assert data["sources"] == []
    assert [source["url"] for source in data["web_sources"]] == [
        "https://example.com/langgraph-1-2",
        "https://example.com/docs",
    ]

    # The search ran on the user's question, and the synthesis prompt carried
    # the fetched page (result 1) and the snippet fallback (result 2).
    assert fake_search.queries == ["what is the latest LangGraph release?"]
    prompt_text = "\n".join(m.content for m in fake_llm.calls[-1])
    assert "durable execution and checkpoints" in prompt_text
    assert "Official documentation." in prompt_text


async def test_explicit_research_command_fast_routes_without_classifier(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    # "research ..." is deterministically fast-routed: the classifier LLM call
    # is skipped entirely, so the only scripted reply is the synthesis.
    fake_llm.replies = ["Answer [1]."]

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "research X"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["agent"] == "research"
    assert len(fake_llm.calls) == 1  # synthesis only, no classification call

    async with db.session() as session:
        result = await session.execute(select(AiExecution))
        features = {row.feature for row in result.scalars().all()}
    assert features == {"agent.research"}


async def test_research_with_no_results_answers_honestly(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_llm: FakeLLMProvider,
    fake_search: FakeSearchProvider,
) -> None:
    token = await _seed_and_login(api, db)
    fake_search.results = []

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "research nothing"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent"] == "research"
    assert "couldn't find any web results" in data["answer"]
    assert data["web_sources"] == []
    # Fast-routed AND no results: the LLM was never invoked at all.
    assert len(fake_llm.calls) == 0


async def test_search_outage_fails_run_with_502(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_llm: FakeLLMProvider,
    fake_search: FakeSearchProvider,
) -> None:
    token = await _seed_and_login(api, db)
    fake_search.fail = True

    response = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "research X"}
    )

    assert response.status_code == 502
    assert "Web search" in response.json()["error"]["message"]

    runs = await api.get("/api/v1/workflows/runs", headers=_auth(token))
    run = runs.json()["data"][0]
    assert run["status"] == "failed"
    assert "Web search" in run["error"]
