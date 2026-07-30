"""Supervisor graph assembly.

Builds the LangGraph state machine: supervisor → (conditional route) → worker
agent → approval gate → END. The shape is driven by a :class:`GraphSpec`, which
is what a workflow version stores — so activating a different version compiles
a different graph rather than merely relabelling the same one.

Compiling with a checkpointer enables the approval gate's pause/resume.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.supervisor.supervisor import SupervisorAgent
from app.workflows.nodes import approval_gate
from app.workflows.spec import GraphSpec, default_spec
from app.workflows.state import AgentState


def build_agent_graph(
    supervisor: SupervisorAgent,
    agents: Mapping[str, BaseAgent],
    checkpointer: Any | None = None,
    spec: GraphSpec | None = None,
) -> Any:
    """Compile the supervisor graph described by ``spec``.

    ``agents`` is everything this process can run; ``spec.agents`` selects the
    subset this version routes to. Omitting the spec compiles the full default
    graph, which keeps direct callers (tests, ad-hoc runs) working without
    inventing a version for them.
    """
    resolved = spec or default_spec(agents)
    enabled = {name: agents[name] for name in resolved.agents if name in agents}
    if not enabled:
        raise ValueError(
            f"None of the spec's agents {resolved.agents} are available in this process"
        )
    fallback = (
        resolved.fallback_agent
        if resolved.fallback_agent in enabled
        else next(iter(enabled))
    )

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor.run)

    if resolved.approval_gate:
        graph.add_node("approval_gate", approval_gate)
        graph.add_edge("approval_gate", END)

    for name, agent in enabled.items():
        graph.add_node(name, agent.run)
        # Without the gate node, workers run straight to completion and
        # `needs_approval` has nothing to act on — which is the point of
        # letting a version turn it off.
        graph.add_edge(name, "approval_gate" if resolved.approval_gate else END)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        # A route the supervisor picked but this version does not enable falls
        # back rather than crashing: the classifier knows the agent catalogue,
        # not this version's subset.
        lambda state: state.get("route") if state.get("route") in enabled else fallback,
        {name: name for name in enabled},
    )
    return graph.compile(checkpointer=checkpointer)
