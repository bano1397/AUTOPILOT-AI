"""Integration tests for the live-run WebSocket endpoint.

Driven through Starlette's real WebSocket test client against the real app, so
these exercise the actual handshake, routing, and JSON frames.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import InMemoryVectorStore
from app.platform.observability import AiExecutionRecorder
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider


@pytest.fixture
def client(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, tmp_path: Path
) -> TestClient:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm = FakeLLMProvider(replies=["general", "Hello!"])
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    # TestClient runs the lifespan, which is where the event stream is bound to
    # the bus in a real process too.
    return TestClient(app)


class TestLiveRunStream:
    def test_a_run_emits_start_steps_and_completion(self, client: TestClient) -> None:
        with client, client.websocket_connect("/ws/runs") as ws:
            response = client.post("/api/v1/agents/ask", json={"message": "hey"})
            assert response.status_code == 200, response.text

            types: list[str] = []
            # Drain until the run finishes; every frame in between is progress.
            while "WorkflowCompleted" not in types:
                message = ws.receive_json()
                if message["type"] != "ping":
                    types.append(message["type"])

        assert types[0] == "WorkflowStarted"
        assert "WorkflowStepCompleted" in types
        assert types[-1] == "WorkflowCompleted"

    def test_step_frames_name_the_node_that_ran(self, client: TestClient) -> None:
        with client, client.websocket_connect("/ws/runs") as ws:
            client.post("/api/v1/agents/ask", json={"message": "hey"})

            nodes: list[str] = []
            while True:
                message = ws.receive_json()
                if message["type"] == "WorkflowStepCompleted":
                    nodes.append(message["data"]["node_name"])
                elif message["type"] == "WorkflowCompleted":
                    break

        assert "supervisor" in nodes

    def test_a_run_scoped_socket_only_receives_its_own_run(
        self, client: TestClient
    ) -> None:
        """Filtering has to happen before the frame reaches the wire.

        Both events are broadcast, the unwanted one first: if the socket
        delivered it, it would be the first frame read.
        """
        from app.domain.events import WorkflowCompleted

        with client, client.websocket_connect("/ws/runs?run_id=target") as ws:
            stream = client.app.state.event_stream
            stream.broadcast(WorkflowCompleted(run_id="other"))
            stream.broadcast(WorkflowCompleted(run_id="target"))

            message = ws.receive_json()

        assert message["data"]["run_id"] == "target"

    def test_an_unscoped_socket_receives_every_run(self, client: TestClient) -> None:
        from app.domain.events import WorkflowCompleted

        with client, client.websocket_connect("/ws/runs") as ws:
            stream = client.app.state.event_stream
            stream.broadcast(WorkflowCompleted(run_id="alpha"))
            stream.broadcast(WorkflowCompleted(run_id="beta"))

            seen = [ws.receive_json()["data"]["run_id"] for _ in range(2)]

        assert seen == ["alpha", "beta"]

    def test_disconnecting_unregisters_the_subscriber(
        self, client: TestClient
    ) -> None:
        """A leaked subscriber would grow the fan-out set forever."""
        with client:
            with client.websocket_connect("/ws/runs"):
                assert client.app.state.event_stream.subscriber_count == 1
            assert client.app.state.event_stream.subscriber_count == 0
