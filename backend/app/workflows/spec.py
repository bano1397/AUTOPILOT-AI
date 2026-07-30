"""The workflow graph specification (blueprint §20).

A :class:`WorkflowVersion` stores one of these as immutable JSON, and
:func:`app.workflows.graph.build_agent_graph` compiles *from* it. That
direction matters: a ``graph_spec`` the executor ignores would be an audit
trail of nothing — versions that look meaningful, roll back cleanly, and change
no behaviour whatsoever. Everything declared here demonstrably alters the
compiled graph, and the lifecycle tests assert exactly that.

The spec is deliberately small. It describes the supervisor topology this
platform actually has — pick a specialist, optionally pause for a human — and
does not pretend to be a general-purpose graph DSL. Arbitrary node wiring is
**not** supported, and inventing that syntax before anything needs it would be
guesswork encoded as schema.

What a version can change:

* ``agents`` — which specialists the supervisor may route to. Narrowing this
  genuinely re-routes traffic: a version listing only ``knowledge`` sends every
  request there.
* ``fallback_agent`` — where an unrecognised route lands.
* ``approval_gate`` — whether the human-in-the-loop node is in the graph at
  all. With it absent, ``needs_approval`` has nothing to act on and no run can
  pause.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The topology name is stored so a future second shape can be added without
# guessing what old rows meant.
SUPERVISOR_TOPOLOGY = "supervisor"


class GraphSpec(BaseModel):
    """An executable description of one workflow version's graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topology: str = SUPERVISOR_TOPOLOGY
    agents: list[str] = Field(min_length=1)
    fallback_agent: str
    approval_gate: bool = True

    @field_validator("topology")
    @classmethod
    def _known_topology(cls, value: str) -> str:
        if value != SUPERVISOR_TOPOLOGY:
            raise ValueError(
                f"Unknown topology {value!r}; only {SUPERVISOR_TOPOLOGY!r} is supported"
            )
        return value

    @field_validator("agents")
    @classmethod
    def _unique_agents(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("agents must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _fallback_is_routable(self) -> GraphSpec:
        # Otherwise an unrecognised route would target a node the graph has no
        # edge to, and the failure would surface at execution time as a
        # LangGraph error rather than here as a rejected version.
        if self.fallback_agent not in self.agents:
            raise ValueError(
                f"fallback_agent {self.fallback_agent!r} must be one of {self.agents}"
            )
        return self

    def validate_against(self, available: Iterable[str]) -> None:
        """Reject agents this deployment cannot actually run.

        Checked when a version is created rather than when it runs: a version
        that cannot compile should never become activatable, and discovering
        that mid-request would fail a user's message instead of an admin's
        edit.
        """
        known = set(available)
        missing = sorted(set(self.agents) - known)
        if missing:
            raise ValueError(
                f"Unknown agent(s) {', '.join(missing)}; "
                f"available: {', '.join(sorted(known))}"
            )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> GraphSpec:
        return cls.model_validate(dict(payload))

    def to_mapping(self) -> dict[str, Any]:
        return self.model_dump()


def default_spec(available: Iterable[str]) -> GraphSpec:
    """The spec matching the graph this platform built before versioning.

    Used to seed the initial version so behaviour is unchanged on upgrade.
    """
    agents = sorted(available)
    fallback = "general" if "general" in agents else agents[0]
    return GraphSpec(agents=agents, fallback_agent=fallback, approval_gate=True)
