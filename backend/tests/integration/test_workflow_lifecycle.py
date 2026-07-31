"""Integration tests for workflow versioning, rollback, clone, history (§20).

The load-bearing assertions are the ones that prove a version is *executable*:
activating a different version must change how a request is routed, and a
paused run must resume under the version it started with.
"""

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


async def _seed_default(api: AsyncClient, fake_llm: FakeLLMProvider) -> dict:
    """Trigger one agent run so the default definition is seeded."""
    fake_llm.replies = ["general", "Hi!"]
    response = await api.post("/api/v1/agents/ask", json={"message": "hey"})
    assert response.status_code == 200, response.text
    definitions = (await api.get("/api/v1/workflows/definitions")).json()["data"]
    assert definitions, "the default definition should be seeded on first run"
    return definitions[0]


class TestSeeding:
    async def test_the_default_definition_is_created_on_first_run(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """An existing deployment gains versioning with no migration step."""
        definition = await _seed_default(api, app.state.llm)

        assert definition["name"] == "agents.ask"

        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        assert detail["active_version"]["version"] == 1
        assert detail["active_version"]["graph_spec"]["approval_gate"] is True

    async def test_the_seeded_spec_covers_every_available_agent(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]

        catalogue = (
            await api.get("/api/v1/workflows/agents-catalogue")
        ).json()["data"]["agents"]

        assert set(detail["active_version"]["graph_spec"]["agents"]) == set(catalogue)

    async def test_runs_pin_the_version_that_produced_them(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        version_id = detail["active_version"]["id"]

        runs = (await api.get("/api/v1/workflows/runs")).json()["data"]

        assert runs[0]["workflow_version_id"] == version_id


class TestVersioning:
    async def test_adding_a_version_supersedes_the_previous_active_one(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)

        created = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "topology": "supervisor",
                    "agents": ["general"],
                    "fallback_agent": "general",
                    "approval_gate": True,
                },
                "notes": "general only",
            },
        )

        assert created.status_code == 201, created.text
        assert created.json()["data"]["version"] == 2

        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        active = [v for v in detail["versions"] if v["is_active"]]
        assert len(active) == 1, "exactly one version may be active"
        assert active[0]["version"] == 2

    async def test_a_version_can_be_staged_without_activating_it(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)

        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "agents": ["general"],
                    "fallback_agent": "general",
                },
                "activate": False,
            },
        )

        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        assert detail["active_version"]["version"] == 1

    async def test_a_spec_naming_an_unknown_agent_is_rejected(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Rejected at write time: a bad version that reached the database
        could be activated and would break every run."""
        definition = await _seed_default(api, app.state.llm)

        response = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {"agents": ["wizard"], "fallback_agent": "wizard"}
            },
        )

        assert response.status_code == 422
        assert "wizard" in response.text

    async def test_an_agent_the_supervisor_cannot_run_is_rejected(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Regression: the catalogue used to return the whole agent registry.

        The email agent is registered but is driven by the triage pipeline, not
        the supervisor graph. A version enabling it passed validation, then
        failed to compile on the next request and 500'd every agent call --
        exactly what write-time validation is supposed to prevent.
        """
        definition = await _seed_default(api, app.state.llm)

        response = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={"graph_spec": {"agents": ["email"], "fallback_agent": "email"}},
        )

        assert response.status_code == 422, response.text

        # And the workflow still runs, on the version that was already active.
        app.state.llm.replies = ["general", "still fine"]
        assert (
            await api.post("/api/v1/agents/ask", json={"message": "hey"})
        ).status_code == 200

    async def test_the_catalogue_lists_only_routable_agents(
        self, api: AsyncClient
    ) -> None:
        catalogue = (
            await api.get("/api/v1/workflows/agents-catalogue")
        ).json()["data"]["agents"]

        assert set(catalogue) == {
            "calendar",
            "general",
            "knowledge",
            "planner",
            "research",
        }
        assert "email" not in catalogue

    async def test_a_malformed_spec_is_rejected(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)

        response = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={"graph_spec": {"agents": ["general"]}},  # no fallback_agent
        )

        assert response.status_code == 422

    async def test_there_is_no_update_endpoint(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Immutability is enforced by absence, not by a runtime check."""
        definition = await _seed_default(api, app.state.llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        version_id = detail["active_version"]["id"]

        response = await api.patch(
            f"/api/v1/workflows/versions/{version_id}",
            json={"graph_spec": {"agents": ["general"], "fallback_agent": "general"}},
        )

        assert response.status_code in (404, 405)


class TestVersionsChangeBehaviour:
    """A version nobody executes is decoration; these pin the wiring."""

    async def test_activating_a_narrowed_version_reroutes_traffic(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake_llm: FakeLLMProvider = app.state.llm
        definition = await _seed_default(api, fake_llm)

        # v2 enables only the knowledge agent, so a "general" classification
        # has nowhere to go and must fall back.
        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "agents": ["knowledge"],
                    "fallback_agent": "knowledge",
                }
            },
        )

        fake_llm.replies = ["general", "unused"]
        response = await api.post("/api/v1/agents/ask", json={"message": "hey"})

        assert response.status_code == 200, response.text
        assert response.json()["data"]["agent"] == "knowledge"

    async def test_rolling_back_restores_the_previous_behaviour(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake_llm: FakeLLMProvider = app.state.llm
        definition = await _seed_default(api, fake_llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        v1_id = detail["active_version"]["id"]

        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "agents": ["knowledge"],
                    "fallback_agent": "knowledge",
                }
            },
        )
        fake_llm.replies = ["general", "unused"]
        narrowed = await api.post("/api/v1/agents/ask", json={"message": "hey"})
        assert narrowed.json()["data"]["agent"] == "knowledge"

        # Rollback == activating the earlier version.
        activated = await api.post(f"/api/v1/workflows/versions/{v1_id}/activate")
        assert activated.status_code == 200, activated.text
        assert activated.json()["data"]["version"] == 1

        fake_llm.replies = ["general", "Hi again!"]
        restored = await api.post("/api/v1/agents/ask", json={"message": "hey"})
        assert restored.json()["data"]["agent"] == "general"

    async def test_rollback_keeps_the_newer_version_available(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Rolling back must itself be reversible, so nothing is deleted."""
        definition = await _seed_default(api, app.state.llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        v1_id = detail["active_version"]["id"]

        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={"graph_spec": {"agents": ["general"], "fallback_agent": "general"}},
        )
        await api.post(f"/api/v1/workflows/versions/{v1_id}/activate")

        after = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        assert [v["version"] for v in after["versions"]] == [1, 2]
        assert after["active_version"]["version"] == 1

    async def test_disabling_the_approval_gate_stops_runs_pausing(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """With the gate node absent, needs_approval has nothing to act on."""
        fake_llm: FakeLLMProvider = app.state.llm
        definition = await _seed_default(api, fake_llm)

        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "agents": ["general"],
                    "fallback_agent": "general",
                    "approval_gate": False,
                }
            },
        )

        fake_llm.replies = ["general", "Answered without review."]
        response = await api.post(
            "/api/v1/agents/ask",
            json={"message": "hey", "require_approval": True},
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "completed"


class TestClone:
    async def test_clone_forks_the_active_spec_and_records_its_origin(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)

        response = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/clone",
            json={"name": "agents.experiment"},
        )

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["definition"]["name"] == "agents.experiment"
        assert data["definition"]["cloned_from_id"] == definition["id"]
        assert data["active_version"]["version"] == 1

    async def test_a_clone_starts_from_the_active_version_not_the_latest(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """Cloning should reproduce what the source currently does, not a
        draft nobody activated."""
        definition = await _seed_default(api, app.state.llm)

        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {"agents": ["general"], "fallback_agent": "general"},
                "activate": False,
            },
        )

        cloned = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/clone",
            json={"name": "agents.fork"},
        )

        spec = cloned.json()["data"]["active_version"]["graph_spec"]
        assert len(spec["agents"]) > 1, "should have cloned v1, not the draft"

    async def test_a_duplicate_name_is_a_conflict(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        definition = await _seed_default(api, app.state.llm)

        response = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/clone",
            json={"name": "agents.ask"},
        )

        assert response.status_code == 409


class TestHistory:
    async def test_runs_are_listed_per_version(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake_llm: FakeLLMProvider = app.state.llm
        definition = await _seed_default(api, fake_llm)
        detail = (
            await api.get(f"/api/v1/workflows/definitions/{definition['id']}")
        ).json()["data"]
        v1_id = detail["active_version"]["id"]

        added = await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={"graph_spec": {"agents": ["general"], "fallback_agent": "general"}},
        )
        v2_id = added.json()["data"]["id"]

        fake_llm.replies = ["general", "second run"]
        await api.post("/api/v1/agents/ask", json={"message": "again"})

        v1_runs = (await api.get(f"/api/v1/workflows/versions/{v1_id}/runs")).json()
        v2_runs = (await api.get(f"/api/v1/workflows/versions/{v2_id}/runs")).json()

        assert v1_runs["meta"]["total"] == 1
        assert v2_runs["meta"]["total"] == 1

    async def test_an_unknown_version_is_404(self, api: AsyncClient) -> None:
        response = await api.get(
            "/api/v1/workflows/versions/00000000-0000-0000-0000-000000000000/runs"
        )

        assert response.status_code == 404


class TestResumeUsesThePinnedVersion:
    """A run must resume under the version it started with.

    Its checkpoint holds node names from the original spec. Resuming into a
    topology someone activated in the meantime would at best rewrite history
    and at worst fail to find the node it paused on.
    """

    async def test_activating_a_new_version_mid_approval_does_not_affect_resume(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        fake_llm: FakeLLMProvider = app.state.llm
        definition = await _seed_default(api, fake_llm)

        # Pause a run under v1, which has the approval gate.
        fake_llm.replies = ["general", "Draft awaiting review."]
        paused = await api.post(
            "/api/v1/agents/ask",
            json={"message": "needs review", "require_approval": True},
        )
        assert paused.status_code == 200, paused.text
        body = paused.json()["data"]
        assert body["status"] == "awaiting_approval"
        approval_id = body["approval_id"]

        # Someone ships a version with no gate while the draft sits in review.
        await api.post(
            f"/api/v1/workflows/definitions/{definition['id']}/versions",
            json={
                "graph_spec": {
                    "agents": ["general"],
                    "fallback_agent": "general",
                    "approval_gate": False,
                }
            },
        )

        # The pending run still resumes cleanly, under v1's graph.
        decided = await api.post(
            f"/api/v1/approvals/{approval_id}/decision", json={"decision": "approved"}
        )

        assert decided.status_code == 200, decided.text
        run = (await api.get("/api/v1/workflows/runs")).json()["data"]
        assert run[0]["status"] == "completed"
