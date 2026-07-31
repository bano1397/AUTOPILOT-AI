"""Integration tests for the Phase 4 operational surface.

`/metrics`, the checkpointer backend selection, and the Redis event bus. The
Redis tests run against a real server when one is reachable and are skipped
otherwise — the same convention the S3 and OCR suites use.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.domain.events import DocumentIndexed, WorkflowCompleted
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import InMemoryVectorStore
from app.platform.events import RedisEventBus
from app.platform.observability import AiExecutionRecorder
from app.workflows.checkpointer import WorkflowCheckpointer, to_psycopg_dsn
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

REDIS_URL = os.getenv("AUTOPILOT_REDIS_URL", "redis://localhost:6379/0")


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, tmp_path: Path
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm = FakeLLMProvider()
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestMetricsEndpoint:
    async def test_serves_the_prometheus_content_type(
        self, api: AsyncClient
    ) -> None:
        """A scraper checks this; the wrong type is silently ignored data."""
        response = await api.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "version=0.0.4" in response.headers["content-type"]

    async def test_http_requests_are_counted(self, api: AsyncClient) -> None:
        await api.get("/health")

        body = (await api.get("/metrics")).text

        assert "autopilot_http_requests_total" in body
        assert 'route="/health"' in body

    async def test_requests_are_labelled_by_template_not_by_path(
        self, api: AsyncClient
    ) -> None:
        """One series per document id would be unbounded cardinality."""
        first = "11111111-1111-1111-1111-111111111111"
        second = "22222222-2222-2222-2222-222222222222"
        await api.get(f"/api/v1/documents/{first}")
        await api.get(f"/api/v1/documents/{second}")

        body = (await api.get("/metrics")).text

        assert "{document_id}" in body
        assert first not in body
        assert second not in body

    async def test_an_unmatched_path_collapses_to_one_series(
        self, api: AsyncClient
    ) -> None:
        """404 paths are attacker-controlled; each must not mint a series."""
        await api.get("/nope/one")
        await api.get("/nope/two")

        body = (await api.get("/metrics")).text

        assert 'route="unmatched"' in body
        assert "/nope/one" not in body

    async def test_ai_calls_are_counted_with_tokens(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake: FakeLLMProvider = app.state.llm
        fake.replies = ["general", "Hi!"]
        await api.post("/api/v1/agents/ask", json={"message": "hey"})

        body = (await api.get("/metrics")).text

        assert "autopilot_ai_calls_total" in body
        assert 'provider="fake"' in body
        assert 'direction="completion"' in body

    async def test_workflow_runs_are_counted(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake: FakeLLMProvider = app.state.llm
        fake.replies = ["general", "Hi!"]
        await api.post("/api/v1/agents/ask", json={"message": "hey"})

        body = (await api.get("/metrics")).text

        assert 'autopilot_workflow_runs_total{status="completed"' in body

    async def test_latency_histograms_are_present(self, api: AsyncClient) -> None:
        await api.get("/health")

        body = (await api.get("/metrics")).text

        assert "autopilot_http_request_duration_seconds_bucket" in body
        assert "autopilot_http_request_duration_seconds_count" in body


class TestCheckpointerBackend:
    def test_sqlite_is_the_default(self) -> None:
        assert WorkflowCheckpointer(":memory:").backend == "sqlite"

    def test_a_postgres_url_selects_postgres(self) -> None:
        """Derived from DATABASE_URL so durable data and durable checkpoints
        cannot drift apart."""
        checkpointer = WorkflowCheckpointer(
            ":memory:", database_url="postgresql+asyncpg://u:p@host/db"
        )

        assert checkpointer.backend == "postgres"

    def test_a_sqlite_url_stays_on_sqlite(self) -> None:
        checkpointer = WorkflowCheckpointer(
            ":memory:", database_url="sqlite+aiosqlite:///./app.db"
        )

        assert checkpointer.backend == "sqlite"

    def test_the_sqlalchemy_driver_suffix_is_stripped_for_psycopg(self) -> None:
        """psycopg rejects `postgresql+asyncpg://` with an unhelpful error."""
        assert (
            to_psycopg_dsn("postgresql+asyncpg://u:p@host/db")
            == "postgresql://u:p@host/db"
        )

    def test_the_asyncpg_ssl_parameter_is_translated(self) -> None:
        """asyncpg spells it `ssl`, libpq spells it `sslmode`; Neon URLs use
        the former and psycopg would reject it."""
        assert to_psycopg_dsn(
            "postgresql+asyncpg://u:p@host/db?ssl=require"
        ).endswith("?sslmode=require")

    async def test_a_missing_postgres_extra_falls_back_rather_than_crashing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Booting on SQLite is better than not booting; the warning is what
        tells an operator checkpoints are no longer durable."""

        async def explode(_: str) -> object:
            raise ImportError("no langgraph-checkpoint-postgres")

        checkpointer = WorkflowCheckpointer(
            ":memory:", database_url="postgresql+asyncpg://u:p@host/db"
        )
        monkeypatch.setattr(checkpointer, "_postgres_context", explode)

        await checkpointer.start()
        try:
            assert checkpointer.saver is not None
        finally:
            await checkpointer.stop()

    async def test_the_readiness_probe_reports_the_backend(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        app.state.checkpointer = WorkflowCheckpointer(":memory:")

        response = await api.get("/health/ready")

        assert response.json()["checks"]["checkpointer"] == "sqlite"


async def _redis_available() -> bool:
    try:
        import redis.asyncio as redis
    except ImportError:
        return False
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await asyncio.wait_for(client.ping(), timeout=2.0)
        await client.aclose()
    except Exception:  # noqa: BLE001 - absence is the thing being detected
        return False
    return True


requires_redis = pytest.mark.skipif(
    not asyncio.run(_redis_available()),
    reason="a reachable Redis (AUTOPILOT_REDIS_URL, default localhost:6379)",
)


class TestRedisBusWithoutRedis:
    """The bus must be usable — and local delivery correct — with no server."""

    async def test_local_delivery_works_when_redis_is_unreachable(self) -> None:
        """Degrading to in-process behaviour is the designed failure mode: a
        cross-replica notification must never fail the request that caused it."""
        bus = RedisEventBus("redis://127.0.0.1:1/0")
        seen: list[str] = []

        async def handler(event: object) -> None:
            seen.append(type(event).__name__)

        bus.subscribe(DocumentIndexed, handler)
        await bus.publish(DocumentIndexed(document_id="d1", chunk_count=2))

        assert seen == ["DocumentIndexed"]

    async def test_start_does_not_raise_when_redis_is_unreachable(self) -> None:
        bus = RedisEventBus("redis://127.0.0.1:1/0")

        await bus.start()
        await bus.stop()


@requires_redis
class TestRedisBus:
    """Opt-in: these need a real Redis."""

    async def test_an_event_reaches_another_replica(self) -> None:
        replica_a = RedisEventBus(REDIS_URL)
        replica_b = RedisEventBus(REDIS_URL)
        received: list[str] = []

        async def handler(event: object) -> None:
            received.append(getattr(event, "run_id", ""))

        replica_b.subscribe(WorkflowCompleted, handler)
        await replica_a.start()
        await replica_b.start()
        try:
            await replica_a.publish(WorkflowCompleted(run_id="run-42"))
            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.05)
        finally:
            await replica_a.stop()
            await replica_b.stop()

        assert received == ["run-42"]

    async def test_a_publisher_does_not_handle_its_own_event_twice(self) -> None:
        """Local delivery happens before mirroring; without the origin check
        the publisher would also receive it back and act on it twice."""
        bus = RedisEventBus(REDIS_URL)
        seen: list[str] = []

        async def handler(event: object) -> None:
            seen.append(getattr(event, "run_id", ""))

        bus.subscribe(WorkflowCompleted, handler)
        await bus.start()
        try:
            await bus.publish(WorkflowCompleted(run_id="run-once"))
            await asyncio.sleep(0.4)
        finally:
            await bus.stop()

        assert seen == ["run-once"]

    async def test_an_unknown_event_type_is_ignored(self) -> None:
        """A rolling deploy can put a newer replica's event on the wire."""
        bus = RedisEventBus(REDIS_URL)
        await bus.start()
        try:
            client = await bus._connect()  # noqa: SLF001 - exercising the wire
            await client.publish(
                "autopilot:events",
                '{"origin":"other","type":"FromTheFuture","data":{}}',
            )
            await asyncio.sleep(0.3)
        finally:
            await bus.stop()

    async def test_a_malformed_payload_does_not_kill_the_consumer(self) -> None:
        bus = RedisEventBus(REDIS_URL)
        received: list[str] = []

        async def handler(event: object) -> None:
            received.append(getattr(event, "run_id", ""))

        bus.subscribe(WorkflowCompleted, handler)
        await bus.start()
        try:
            client = await bus._connect()  # noqa: SLF001 - exercising the wire
            await client.publish("autopilot:events", "not json at all")
            await asyncio.sleep(0.2)
            # The consumer must still be alive to deliver the next event.
            await client.publish(
                "autopilot:events",
                '{"origin":"other","type":"WorkflowCompleted",'
                '"data":{"run_id":"still-alive"}}',
            )
            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.05)
        finally:
            await bus.stop()

        assert received == ["still-alive"]
