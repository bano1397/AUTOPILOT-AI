"""Typed shared state for agent graphs.

``total=False`` lets nodes return partial updates; LangGraph merges them into
the shared state. Values are JSON-friendly so state can be checkpointed and
inspected later (workflow persistence arrives in M4).
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state flowing through the supervisor graph."""

    user_id: str
    request: str
    # Prior conversation turns as role/content dicts (oldest first).
    history: list[dict[str, str]]
    # Set by the supervisor: registry name of the agent to run.
    route: str
    # Set by the executing agent.
    agent: str
    answer: str
    model: str | None
    grounded: bool
    # Document citations (RAG) and web citations (research), respectively.
    sources: list[dict[str, Any]]
    web_sources: list[dict[str, Any]]
    error: str | None
    # Human-in-the-loop: set on the initial state to pause at the approval
    # gate; the gate records the reviewer's decision.
    needs_approval: bool
    approval_decision: str
