"""Integration tests: events become in-app notifications; the API manages them."""

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


async def _notifications(api: AsyncClient) -> list[dict[str, object]]:
    response = await api.get("/api/v1/notifications")
    assert response.status_code == 200
    return list(response.json()["data"])


async def test_document_indexing_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    upload = await api.post(
        "/api/v1/documents",
        files={"file": ("handbook.txt", b"Policy text. " * 100, "text/plain")},
    )
    assert upload.status_code == 201

    items = await _notifications(api)
    assert len(items) == 1
    assert items[0]["type"] == "document_indexed"
    assert "handbook.txt" in str(items[0]["body"])
    assert items[0]["read"] is False


async def test_approval_request_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = ["general", "Draft."]

    ask = await api.post(
        "/api/v1/agents/ask",
        json={"message": "draft this", "require_approval": True},
    )
    assert ask.status_code == 200

    items = await _notifications(api)
    kinds = {item["type"] for item in items}
    assert "approval_required" in kinds


async def test_workflow_failure_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.fail = True

    with pytest.raises(RuntimeError, match="llm service unavailable"):
        await api.post(
            "/api/v1/agents/ask", json={"message": "hi"}
        )

    items = await _notifications(api)
    assert any(item["type"] == "workflow_failed" for item in items)
    failure = next(item for item in items if item["type"] == "workflow_failed")
    assert "llm service unavailable" in str(failure["body"])


async def test_unread_count_and_mark_read_flow(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    for name in ("a.txt", "b.txt"):
        response = await api.post(
            "/api/v1/documents",
            files={"file": (name, b"Content. " * 100, "text/plain")},
        )
        assert response.status_code == 201

    count = await api.get("/api/v1/notifications/unread-count")
    assert count.json()["data"]["count"] == 2

    items = await _notifications(api)
    marked = await api.post(
        f"/api/v1/notifications/{items[0]['id']}/read"
    )
    assert marked.status_code == 200
    assert marked.json()["data"]["read"] is True

    count_after = await api.get(
        "/api/v1/notifications/unread-count"
    )
    assert count_after.json()["data"]["count"] == 1

    read_all = await api.post("/api/v1/notifications/read-all")
    assert read_all.json()["data"]["updated"] == 1
    final = await api.get("/api/v1/notifications/unread-count")
    assert final.json()["data"]["count"] == 0

