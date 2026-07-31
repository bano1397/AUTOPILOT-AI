"""Integration tests for the streamed grounded answer (`POST /rag/ask/stream`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.embeddings.stub import StubEmbeddingProvider
from app.infrastructure.llm.stub import StubLLMProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import InMemoryVectorStore
from app.platform.observability import AiExecutionRecorder
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, tmp_path: Path
) -> TestClient:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = StubEmbeddingProvider(dimensions=256)
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm = StubLLMProvider()
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    return TestClient(app)


def _parse_sse(body: str) -> list[tuple[str, object]]:
    """Turn a raw SSE body into (event, payload) pairs."""
    frames: list[tuple[str, object]] = []
    event: str | None = None
    for line in body.splitlines():
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:") and event is not None:
            frames.append((event, json.loads(line[len("data:") :].strip())))
            event = None
    return frames


def _upload(client: TestClient, text: str) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("policy.txt", text.encode(), "text/plain")},
    )
    assert response.status_code == 201, response.text


class TestStreamedAnswer:
    def test_sources_arrive_before_any_text(self, client: TestClient) -> None:
        """So the UI can render citations while the answer is still coming in,
        and a reader can judge grounding before trusting the prose."""
        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            response = client.post(
                "/api/v1/rag/ask/stream", json={"query": "vacation days"}
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        frames = _parse_sse(response.text)
        assert frames[0][0] == "sources"
        assert frames[-1][0] == "done"

    def test_the_reply_arrives_in_multiple_deltas(self, client: TestClient) -> None:
        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            response = client.post(
                "/api/v1/rag/ask/stream", json={"query": "vacation days"}
            )

        deltas = [payload for event, payload in _parse_sse(response.text) if event == "delta"]

        assert len(deltas) > 1, "a streamed answer should not arrive in one lump"

    def test_the_streamed_text_matches_the_non_streamed_answer(
        self, client: TestClient
    ) -> None:
        """The two endpoints must not disagree about what the answer is."""
        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            streamed = client.post(
                "/api/v1/rag/ask/stream", json={"query": "vacation days"}
            )
            plain = client.post("/api/v1/rag/ask", json={"query": "vacation days"})

        joined = "".join(
            str(payload)
            for event, payload in _parse_sse(streamed.text)
            if event == "delta"
        )
        assert joined == plain.json()["data"]["answer"]

    def test_sources_carry_the_same_citation_fields_as_the_plain_endpoint(
        self, client: TestClient
    ) -> None:
        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            response = client.post(
                "/api/v1/rag/ask/stream", json={"query": "vacation days"}
            )

        sources = next(
            payload for event, payload in _parse_sse(response.text) if event == "sources"
        )
        assert isinstance(sources, list) and sources
        first = sources[0]
        assert {"document_id", "filename", "chunk_index", "text", "retrieval"} <= set(
            first
        )

    def test_the_done_frame_reports_grounding(self, client: TestClient) -> None:
        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            response = client.post(
                "/api/v1/rag/ask/stream", json={"query": "vacation days"}
            )

        done = next(
            payload for event, payload in _parse_sse(response.text) if event == "done"
        )
        assert isinstance(done, dict)
        assert done["grounded"] is True
        assert done["model"] == "stub"

    def test_no_documents_yields_an_honest_ungrounded_answer(
        self, client: TestClient
    ) -> None:
        with client:
            response = client.post(
                "/api/v1/rag/ask/stream", json={"query": "anything at all"}
            )

        frames = _parse_sse(response.text)
        done = next(payload for event, payload in frames if event == "done")

        assert isinstance(done, dict)
        assert done["grounded"] is False
        assert any(event == "sources" and payload == [] for event, payload in frames)


class TestStreamedCallsAreAudited:
    async def test_a_streamed_call_records_an_execution_with_usage(
        self, client: TestClient, db: SqlAlchemyDatabaseProvider
    ) -> None:
        """A streamed answer must be as auditable as a one-shot one, or the
        cost dashboard quietly under-reports as soon as streaming ships.

        Asserted against the table rather than the analytics API, which
        aggregates: the question here is whether the row was written at all,
        with real token counts on it.
        """
        from app.platform.observability.models import AiExecution
        from sqlalchemy import select

        with client:
            _upload(client, "Employees receive twenty vacation days per year.")
            client.post("/api/v1/rag/ask/stream", json={"query": "vacation days"})

        async with db.session() as session:
            rows = (
                (await session.execute(select(AiExecution).where(AiExecution.feature == "rag.ask")))
                .scalars()
                .all()
            )

        assert rows, "the streamed call should appear in the audit trail"
        row = rows[0]
        assert row.completion_tokens > 0
        assert row.provider == "stub"
        assert row.error is None
        assert row.prompt_key == "rag.ask.system"
