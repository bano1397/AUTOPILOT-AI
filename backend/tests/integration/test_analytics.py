"""Integration tests for the analytics overview."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest_asyncio
from app.features.documents.models import Document, DocumentStatus
from app.features.tasks.models import Task, TaskPriority
from app.features.workflows.models import WorkflowRun, WorkflowRunStatus
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.platform.observability.models import AiExecution
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import workspace_user_id


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed_executions(db: SqlAlchemyDatabaseProvider, user_id: UUID) -> None:
    async with db.session() as session:
        session.add_all(
            [
                AiExecution(
                    user_id=user_id,
                    feature="rag.ask",
                    provider="ollama",
                    model="llama3.2",
                    prompt="p",
                    prompt_tokens=100,
                    completion_tokens=40,
                    cost_usd=0.0,
                    duration_ms=1200,
                ),
                AiExecution(
                    user_id=user_id,
                    feature="agent.research",
                    provider="ollama",
                    model="llama3.2",
                    prompt="p",
                    prompt_tokens=200,
                    completion_tokens=60,
                    cost_usd=0.0,
                    duration_ms=800,
                    error="boom",
                ),
            ]
        )
        session.add(
            WorkflowRun(
                user_id=user_id,
                workflow_name="agents.ask",
                status=WorkflowRunStatus.COMPLETED,
            )
        )
        session.add(
            Document(
                user_id=user_id,
                filename="d.txt",
                mime_type="text/plain",
                size_bytes=10,
                status=DocumentStatus.INDEXED,
                storage_path="a/b.txt",
                doc_metadata={},
            )
        )
        session.add(
            Task(user_id=user_id, title="t", priority=TaskPriority.LOW)
        )
        await session.commit()


async def test_overview_aggregates_usage(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    user_id = await workspace_user_id(db)
    await _seed_executions(db, user_id)

    response = await api.get("/api/v1/analytics/overview?days=30")

    assert response.status_code == 200
    data = response.json()["data"]
    totals = data["totals"]
    assert totals["executions"] == 2
    assert totals["prompt_tokens"] == 300
    assert totals["completion_tokens"] == 100
    assert totals["total_tokens"] == 400
    assert totals["errors"] == 1
    assert totals["error_rate"] == 0.5
    assert totals["avg_duration_ms"] == 1000

    features = {f["feature"]: f for f in data["by_feature"]}
    assert set(features) == {"rag.ask", "agent.research"}
    assert features["agent.research"]["total_tokens"] == 260

    assert data["by_model"][0]["model"] == "llama3.2"
    assert data["by_model"][0]["executions"] == 2

    # The time series spans the whole window and ends today with the activity.
    assert len(data["timeseries"]) == 30
    assert data["timeseries"][-1]["executions"] == 2

    entities = data["entities"]
    assert entities["documents_indexed"] == 1
    assert {s["status"]: s["count"] for s in entities["workflow_runs"]} == {
        "completed": 1
    }
    assert {s["status"]: s["count"] for s in entities["tasks"]} == {"todo": 1}


async def test_days_bounds_are_validated(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    too_many = await api.get("/api/v1/analytics/overview?days=999")
    assert too_many.status_code == 422
