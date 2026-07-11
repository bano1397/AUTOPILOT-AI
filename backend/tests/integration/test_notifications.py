"""Integration tests: events become in-app notifications; the API manages them."""

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
from app.workflows.checkpointer import WorkflowCheckpointer
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider, FakeVectorStore

_ALICE = ("alice@example.com", "alicepass1")
_BOB = ("bob@example.com", "bobpass123")


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


async def _notifications(api: AsyncClient, token: str) -> list[dict[str, object]]:
    response = await api.get("/api/v1/notifications", headers=_auth(token))
    assert response.status_code == 200
    return list(response.json()["data"])


async def test_document_indexing_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)

    upload = await api.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": ("handbook.txt", b"Policy text. " * 100, "text/plain")},
    )
    assert upload.status_code == 201

    items = await _notifications(api, token)
    assert len(items) == 1
    assert items[0]["type"] == "document_indexed"
    assert "handbook.txt" in str(items[0]["body"])
    assert items[0]["read"] is False


async def test_approval_request_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.replies = ["general", "Draft."]

    ask = await api.post(
        "/api/v1/agents/ask",
        headers=_auth(token),
        json={"message": "draft this", "require_approval": True},
    )
    assert ask.status_code == 200

    items = await _notifications(api, token)
    kinds = {item["type"] for item in items}
    assert "approval_required" in kinds


async def test_workflow_failure_creates_notification(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, fake_llm: FakeLLMProvider
) -> None:
    token = await _seed_and_login(api, db)
    fake_llm.fail = True

    with pytest.raises(RuntimeError, match="llm service unavailable"):
        await api.post(
            "/api/v1/agents/ask", headers=_auth(token), json={"message": "hi"}
        )

    items = await _notifications(api, token)
    assert any(item["type"] == "workflow_failed" for item in items)
    failure = next(item for item in items if item["type"] == "workflow_failed")
    assert "llm service unavailable" in str(failure["body"])


async def test_unread_count_and_mark_read_flow(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    token = await _seed_and_login(api, db)
    for name in ("a.txt", "b.txt"):
        response = await api.post(
            "/api/v1/documents",
            headers=_auth(token),
            files={"file": (name, b"Content. " * 100, "text/plain")},
        )
        assert response.status_code == 201

    count = await api.get("/api/v1/notifications/unread-count", headers=_auth(token))
    assert count.json()["data"]["count"] == 2

    items = await _notifications(api, token)
    marked = await api.post(
        f"/api/v1/notifications/{items[0]['id']}/read", headers=_auth(token)
    )
    assert marked.status_code == 200
    assert marked.json()["data"]["read"] is True

    count_after = await api.get(
        "/api/v1/notifications/unread-count", headers=_auth(token)
    )
    assert count_after.json()["data"]["count"] == 1

    read_all = await api.post("/api/v1/notifications/read-all", headers=_auth(token))
    assert read_all.json()["data"]["updated"] == 1
    final = await api.get("/api/v1/notifications/unread-count", headers=_auth(token))
    assert final.json()["data"]["count"] == 0


async def test_notifications_are_owner_scoped(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    alice = await _seed_and_login(api, db)
    bob = await _seed_and_login(api, db, *_BOB)
    upload = await api.post(
        "/api/v1/documents",
        headers=_auth(alice),
        files={"file": ("mine.txt", b"Content. " * 100, "text/plain")},
    )
    assert upload.status_code == 201
    alice_items = await _notifications(api, alice)
    assert len(alice_items) == 1

    # Bob sees nothing and cannot mark Alice's notification.
    assert await _notifications(api, bob) == []
    hijack = await api.post(
        f"/api/v1/notifications/{alice_items[0]['id']}/read", headers=_auth(bob)
    )
    assert hijack.status_code == 404


async def test_notifications_require_authentication(api: AsyncClient) -> None:
    listing = await api.get("/api/v1/notifications")
    count = await api.get("/api/v1/notifications/unread-count")
    mark = await api.post(f"/api/v1/notifications/{uuid4()}/read")
    assert listing.status_code == 401
    assert count.status_code == 401
    assert mark.status_code == 401
