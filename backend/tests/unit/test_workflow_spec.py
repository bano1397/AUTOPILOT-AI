"""Unit tests for the workflow graph specification and its compilation.

The point of these: a ``graph_spec`` that the graph builder ignores would be an
audit trail of nothing. These assert the spec genuinely shapes the compiled
graph.
"""

from __future__ import annotations

import pytest
from app.workflows.graph import build_agent_graph
from app.workflows.spec import SUPERVISOR_TOPOLOGY, GraphSpec, default_spec
from pydantic import ValidationError


class _Agent:
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        return {"agent": self.name, "answer": f"from {self.name}"}


class _Supervisor:
    async def run(self, state: dict[str, object]) -> dict[str, object]:
        return {"route": state.get("route", "general")}


def _agents(*names: str) -> dict[str, _Agent]:
    return {name: _Agent(name) for name in names}


class TestSpecValidation:
    def test_a_valid_spec_round_trips(self) -> None:
        spec = GraphSpec(
            agents=["knowledge", "general"], fallback_agent="general"
        )

        assert GraphSpec.from_mapping(spec.to_mapping()) == spec

    def test_fallback_must_be_one_of_the_agents(self) -> None:
        """Otherwise an unrecognised route targets a node with no edge, and the
        failure surfaces at execution time instead of at write time."""
        with pytest.raises(ValueError, match="fallback_agent"):
            GraphSpec(agents=["knowledge"], fallback_agent="general")

    def test_agents_must_not_be_empty(self) -> None:
        with pytest.raises(ValueError):
            GraphSpec(agents=[], fallback_agent="general")

    def test_duplicate_agents_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicates"):
            GraphSpec(agents=["general", "general"], fallback_agent="general")

    def test_unknown_topology_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="topology"):
            GraphSpec(
                topology="mesh", agents=["general"], fallback_agent="general"
            )

    def test_unknown_keys_are_rejected(self) -> None:
        """A typo'd field must not be silently stored as part of an immutable
        version."""
        with pytest.raises(ValueError):
            GraphSpec.from_mapping(
                {
                    "agents": ["general"],
                    "fallback_agent": "general",
                    "aproval_gate": True,
                }
            )

    def test_validate_against_rejects_unavailable_agents(self) -> None:
        spec = GraphSpec(agents=["general", "wizard"], fallback_agent="general")

        with pytest.raises(ValueError, match="wizard"):
            spec.validate_against(["general", "knowledge"])

    def test_validate_against_accepts_a_subset(self) -> None:
        spec = GraphSpec(agents=["general"], fallback_agent="general")

        spec.validate_against(["general", "knowledge", "research"])

    def test_spec_is_frozen(self) -> None:
        """Immutability is the property versions rest on."""
        spec = GraphSpec(agents=["general"], fallback_agent="general")

        with pytest.raises(ValidationError):
            spec.agents = ["knowledge"]  # type: ignore[misc]


class TestDefaultSpec:
    def test_includes_every_available_agent(self) -> None:
        spec = default_spec(["knowledge", "general", "research"])

        assert set(spec.agents) == {"knowledge", "general", "research"}
        assert spec.topology == SUPERVISOR_TOPOLOGY
        assert spec.approval_gate is True

    def test_prefers_general_as_the_fallback(self) -> None:
        assert default_spec(["knowledge", "general"]).fallback_agent == "general"

    def test_falls_back_to_any_agent_when_general_is_absent(self) -> None:
        spec = default_spec(["knowledge", "research"])

        assert spec.fallback_agent in spec.agents


class TestSpecShapesTheGraph:
    """The spec must change the compiled graph, not merely describe it."""

    def test_only_the_specified_agents_become_nodes(self) -> None:
        agents = _agents("knowledge", "general", "research", "planner")
        spec = GraphSpec(agents=["knowledge", "general"], fallback_agent="general")

        graph = build_agent_graph(_Supervisor(), agents, spec=spec)  # type: ignore[arg-type]
        nodes = set(graph.get_graph().nodes)

        assert {"knowledge", "general"} <= nodes
        assert "research" not in nodes
        assert "planner" not in nodes

    def test_the_approval_gate_can_be_removed(self) -> None:
        agents = _agents("general")
        with_gate = GraphSpec(agents=["general"], fallback_agent="general")
        without = GraphSpec(
            agents=["general"], fallback_agent="general", approval_gate=False
        )

        assert "approval_gate" in set(
            build_agent_graph(_Supervisor(), agents, spec=with_gate)  # type: ignore[arg-type]
            .get_graph()
            .nodes
        )
        assert "approval_gate" not in set(
            build_agent_graph(_Supervisor(), agents, spec=without)  # type: ignore[arg-type]
            .get_graph()
            .nodes
        )

    def test_omitting_the_spec_compiles_the_full_default_graph(self) -> None:
        agents = _agents("knowledge", "general", "research")

        nodes = set(build_agent_graph(_Supervisor(), agents).get_graph().nodes)  # type: ignore[arg-type]

        assert {"knowledge", "general", "research", "approval_gate"} <= nodes

    def test_a_spec_naming_no_available_agent_is_rejected(self) -> None:
        """Better a loud failure at compile time than a graph with no workers."""
        spec = GraphSpec(agents=["wizard"], fallback_agent="wizard")

        with pytest.raises(ValueError, match="available"):
            build_agent_graph(_Supervisor(), _agents("general"), spec=spec)  # type: ignore[arg-type]


class TestRoutingHonoursTheSpec:
    async def test_a_route_the_version_disables_falls_back(self) -> None:
        """The classifier knows the whole agent catalogue, not this version's
        subset, so it can legitimately pick a disabled agent."""
        agents = _agents("knowledge", "general")
        spec = GraphSpec(agents=["knowledge"], fallback_agent="knowledge")
        graph = build_agent_graph(_Supervisor(), agents, spec=spec)  # type: ignore[arg-type]

        result = await graph.ainvoke({"route": "general", "request": "hi"})

        assert result["agent"] == "knowledge"

    async def test_an_enabled_route_is_honoured(self) -> None:
        agents = _agents("knowledge", "general")
        spec = GraphSpec(agents=["knowledge", "general"], fallback_agent="general")
        graph = build_agent_graph(_Supervisor(), agents, spec=spec)  # type: ignore[arg-type]

        result = await graph.ainvoke({"route": "knowledge", "request": "hi"})

        assert result["agent"] == "knowledge"
