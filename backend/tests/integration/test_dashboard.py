"""Integration tests for the dashboard aggregate endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import InMemoryVectorStore
from app.platform.observability import AiExecutionRecorder
from app.workflows.checkpointer import WorkflowCheckpointer
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider


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
    checkpointer: WorkflowCheckpointer,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.checkpointer = checkpointer
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm = FakeLLMProvider()
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestDashboard:
    async def test_returns_all_three_sections_in_one_call(
        self, api: AsyncClient
    ) -> None:
        """The point of the endpoint: one round trip instead of three."""
        response = await api.get("/api/v1/dashboard")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert {
            "analytics",
            "pending_approvals",
            "pending_approval_count",
            "agents",
            "recent_runs",
        } == set(data)

    async def test_agents_match_the_agents_endpoint(self, api: AsyncClient) -> None:
        """A read view must not drift from the page it summarises."""
        dashboard = (await api.get("/api/v1/dashboard")).json()["data"]
        agents = (await api.get("/api/v1/agents")).json()["data"]

        assert {a["name"] for a in dashboard["agents"]} == {
            a["name"] for a in agents
        }

    async def test_analytics_match_the_analytics_endpoint(
        self, api: AsyncClient
    ) -> None:
        dashboard = (await api.get("/api/v1/dashboard")).json()["data"]
        overview = (await api.get("/api/v1/analytics/overview")).json()["data"]

        assert dashboard["analytics"]["days"] == overview["days"]
        assert (
            dashboard["analytics"]["totals"]["executions"]
            == overview["totals"]["executions"]
        )

    async def test_the_window_is_configurable(self, api: AsyncClient) -> None:
        response = await api.get("/api/v1/dashboard", params={"days": 7})

        assert response.json()["data"]["analytics"]["days"] == 7

    async def test_an_out_of_range_window_is_rejected(self, api: AsyncClient) -> None:
        assert (
            await api.get("/api/v1/dashboard", params={"days": 500})
        ).status_code == 422

    async def test_pending_approvals_appear_with_a_total(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake: FakeLLMProvider = app.state.llm
        fake.replies = ["general", "A draft for review."]

        paused = await api.post(
            "/api/v1/agents/ask",
            json={"message": "needs review", "require_approval": True},
        )
        assert paused.json()["data"]["status"] == "awaiting_approval"

        data = (await api.get("/api/v1/dashboard")).json()["data"]

        assert data["pending_approval_count"] == 1
        assert len(data["pending_approvals"]) == 1
        assert data["pending_approvals"][0]["status"] == "pending"

    async def test_the_preview_is_capped_but_the_count_is_not(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """The dashboard shows a preview; the Approvals page pages the queue."""
        fake: FakeLLMProvider = app.state.llm
        for index in range(7):
            fake.replies = ["general", f"Draft {index}"]
            await api.post(
                "/api/v1/agents/ask",
                json={"message": f"review {index}", "require_approval": True},
            )

        data = (await api.get("/api/v1/dashboard")).json()["data"]

        assert data["pending_approval_count"] == 7
        assert len(data["pending_approvals"]) == 5

    async def test_an_empty_workspace_returns_empty_sections_not_an_error(
        self, api: AsyncClient
    ) -> None:
        data = (await api.get("/api/v1/dashboard")).json()["data"]

        assert data["pending_approvals"] == []
        assert data["pending_approval_count"] == 0
        assert data["analytics"]["totals"]["executions"] == 0
        assert data["agents"], "agents come from the registry, not from data"


class TestRecentRuns:
    async def test_runs_appear_and_match_the_runs_endpoint(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Included so the activity feed reads from the same snapshot as the
        KPIs above it, rather than fetching separately and disagreeing."""
        fake: FakeLLMProvider = app.state.llm
        fake.replies = ["general", "Hello!"]
        await api.post("/api/v1/agents/ask", json={"message": "hey"})

        dashboard = (await api.get("/api/v1/dashboard")).json()["data"]
        runs = (await api.get("/api/v1/workflows/runs")).json()["data"]

        assert len(dashboard["recent_runs"]) == 1
        assert dashboard["recent_runs"][0]["id"] == runs[0]["id"]

    async def test_the_preview_is_capped(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake: FakeLLMProvider = app.state.llm
        for index in range(10):
            fake.replies = ["general", f"Reply {index}"]
            await api.post("/api/v1/agents/ask", json={"message": f"msg {index}"})

        data = (await api.get("/api/v1/dashboard")).json()["data"]

        assert len(data["recent_runs"]) == 8
