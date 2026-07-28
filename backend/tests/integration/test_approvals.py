"""Integration tests for human-in-the-loop approvals (pause/resume)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecutionRecorder
from app.workflows.checkpointer import WorkflowCheckpointer
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest_asyncio.fixture
async def checkpointer() -> AsyncIterator[WorkflowCheckpointer]:
    saver = WorkflowCheckpointer(":memory:")
    await saver.start()
    yield saver
    await saver.stop()


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_llm: FakeLLMProvider,
    checkpointer: WorkflowCheckpointer,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.llm = fake_llm
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    app.state.checkpointer = checkpointer
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _ask_with_approval(
    api: AsyncClient, fake_llm: FakeLLMProvider
) -> dict[str, object]:
    fake_llm.replies = ["general", "Draft answer for review."]
    response = await api.post(
        "/api/v1/agents/ask",
        json={"message": "draft something for me", "require_approval": True},
    )
    assert response.status_code == 200
    return dict(response.json()["data"])


async def test_require_approval_pauses_run_with_draft(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:

    data = await _ask_with_approval(api, fake_llm)

    assert data["status"] == "awaiting_approval"
    assert data["approval_id"]
    assert data["answer"] == "Draft answer for review."

    # The run is paused, not completed.
    run = await api.get(
        f"/api/v1/workflows/runs/{data['run_id']}"
    )
    assert run.json()["data"]["run"]["status"] == "awaiting_approval"
    assert run.json()["data"]["run"]["ended_at"] is None

    # Nothing was committed to the conversation while paused.
    conversation = await api.get(
        f"/api/v1/conversations/{data['conversation_id']}"
    )
    assert conversation.json()["data"]["messages"] == []

    # The approval is listed as pending.
    pending = await api.get("/api/v1/approvals")
    assert pending.json()["meta"]["total"] == 1
    assert pending.json()["data"][0]["id"] == data["approval_id"]
    assert pending.json()["data"][0]["payload"]["draft_answer"] == "Draft answer for review."


async def test_approving_resumes_and_records_conversation(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    data = await _ask_with_approval(api, fake_llm)

    decision = await api.post(
        f"/api/v1/approvals/{data['approval_id']}/decision",
        json={"decision": "approved"},
    )

    assert decision.status_code == 200
    body = decision.json()["data"]
    assert body["approval"]["status"] == "approved"
    assert body["answer"] == "Draft answer for review."

    run = await api.get(f"/api/v1/workflows/runs/{data['run_id']}")
    run_data = run.json()["data"]
    assert run_data["run"]["status"] == "completed"
    assert run_data["run"]["ended_at"] is not None
    node_names = [step["node_name"] for step in run_data["steps"]]
    assert node_names == ["supervisor", "general", "approval_gate"]

    conversation = await api.get(
        f"/api/v1/conversations/{data['conversation_id']}"
    )
    messages = conversation.json()["data"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Draft answer for review."
    assert messages[1]["meta"]["decision"] == "approved"

    # The approval is no longer pending.
    pending = await api.get("/api/v1/approvals")
    assert pending.json()["meta"]["total"] == 0


async def test_rejecting_discards_draft(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    data = await _ask_with_approval(api, fake_llm)

    decision = await api.post(
        f"/api/v1/approvals/{data['approval_id']}/decision",
        json={"decision": "rejected"},
    )

    assert decision.status_code == 200
    body = decision.json()["data"]
    assert body["approval"]["status"] == "rejected"
    assert "rejected" in body["answer"]
    assert body["sources"] == []

    conversation = await api.get(
        f"/api/v1/conversations/{data['conversation_id']}"
    )
    messages = conversation.json()["data"]["messages"]
    assert messages[1]["meta"]["decision"] == "rejected"
    assert "rejected" in messages[1]["content"]


async def test_double_decision_conflicts(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    data = await _ask_with_approval(api, fake_llm)
    first = await api.post(
        f"/api/v1/approvals/{data['approval_id']}/decision",
        json={"decision": "approved"},
    )
    assert first.status_code == 200

    second = await api.post(
        f"/api/v1/approvals/{data['approval_id']}/decision",
        json={"decision": "rejected"},
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


async def test_ask_without_approval_is_unchanged(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = ["general", "Hello!"]

    response = await api.post(
        "/api/v1/agents/ask", json={"message": "hi"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["approval_id"] is None
    pending = await api.get("/api/v1/approvals")
    assert pending.json()["meta"]["total"] == 0

