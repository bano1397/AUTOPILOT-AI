"""Supervisor graph assembly.

Builds the LangGraph state machine: supervisor → (conditional route) → worker
agent → approval gate → END. Generic over the agents mapping, so adding a new
agent is one entry — no graph rewiring. Compiling with a checkpointer enables
the approval gate's pause/resume.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.supervisor.supervisor import ROUTE_GENERAL, SupervisorAgent
from app.workflows.nodes import approval_gate
from app.workflows.state import AgentState


def build_agent_graph(
    supervisor: SupervisorAgent,
    agents: Mapping[str, BaseAgent],
    checkpointer: Any | None = None,
) -> Any:
    """Compile the supervisor graph over the given worker agents."""
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor.run)
    graph.add_node("approval_gate", approval_gate)
    for name, agent in agents.items():
        graph.add_node(name, agent.run)
        graph.add_edge(name, "approval_gate")
    graph.add_edge("approval_gate", END)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        # An unknown route falls back to the general agent rather than crashing.
        lambda state: state.get("route") if state.get("route") in agents else ROUTE_GENERAL,
        {name: name for name in agents},
    )
    return graph.compile(checkpointer=checkpointer)
