"""Integration tests for workflow run persistence and the runs API."""

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


async def test_ask_creates_completed_run_with_steps(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "Hello!"]

    ask = await api.post(
        "/api/v1/agents/ask", headers=_auth(token), json={"message": "hi"}
    )
    assert ask.status_code == 200
    run_id = ask.json()["data"]["run_id"]

    detail = await api.get(f"/api/v1/workflows/runs/{run_id}", headers=_auth(token))
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["run"]["workflow_name"] == "agents.ask"
    assert data["run"]["status"] == "completed"
    assert data["run"]["ended_at"] is not None
    assert data["run"]["duration_ms"] is not None
    assert data["input"]["message"] == "hi"
    assert data["output"]["agent"] == "general"
    assert data["output"]["answer_preview"] == "Hello!"
    node_names = [step["node_name"] for step in data["steps"]]
    assert node_names == ["supervisor", "general", "approval_gate"]
    assert [step["position"] for step in data["steps"]] == [0, 1, 2]


async def test_failed_run_is_recorded_and_error_propagates(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.fail = True

    # A supervisor failure is an unexpected error (500 path). Starlette's
    # ServerErrorMiddleware re-raises after responding, and ASGITransport
    # propagates that to the test client — so expect the raise here.
    with pytest.raises(RuntimeError, match="llm service unavailable"):
        await api.post(
            "/api/v1/agents/ask", headers=_auth(token), json={"message": "hi"}
        )

    runs = await api.get("/api/v1/workflows/runs", headers=_auth(token))
    assert runs.status_code == 200
    body = runs.json()
    assert body["meta"]["total"] == 1
    run = body["data"][0]
    assert run["status"] == "failed"
    assert "llm service unavailable" in run["error"]


async def test_runs_list_is_owner_scoped(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    alice = await _seed_and_login(api, db)
    bob = await _seed_and_login(api, db, *_BOB)
    fake_llm.replies = ["general", "hi"]
    ask = await api.post(
        "/api/v1/agents/ask", headers=_auth(alice), json={"message": "hello"}
    )
    run_id = ask.json()["data"]["run_id"]

    bob_list = await api.get("/api/v1/workflows/runs", headers=_auth(bob))
    assert bob_list.json()["meta"]["total"] == 0

    bob_detail = await api.get(f"/api/v1/workflows/runs/{run_id}", headers=_auth(bob))
    assert bob_detail.status_code == 404


async def test_unknown_run_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)
    response = await api.get(f"/api/v1/workflows/runs/{uuid4()}", headers=_auth(token))
    assert response.status_code == 404


async def test_runs_endpoints_require_authentication(api: AsyncClient) -> None:
    listing = await api.get("/api/v1/workflows/runs")
    detail = await api.get(f"/api/v1/workflows/runs/{uuid4()}")
    assert listing.status_code == 401
    assert detail.status_code == 401
