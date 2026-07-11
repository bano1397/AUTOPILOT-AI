"""Reusable graph nodes."""

from __future__ import annotations

from langgraph.types import interrupt

from app.workflows.state import AgentState

APPROVAL_ACTION_ANSWER_REVIEW = "agents.answer_review"


async def approval_gate(state: AgentState) -> AgentState:
    """Pause for human review when the state requires approval.

    Pass-through when ``needs_approval`` is not set. Otherwise the graph is
    interrupted (checkpointed) until a decision arrives via
    ``Command(resume=<decision>)``: an approved draft continues unchanged; a
    rejected one has its answer replaced and its sources dropped.
    """
    if not state.get("needs_approval"):
        return {}

    decision = interrupt(
        {
            "action_type": APPROVAL_ACTION_ANSWER_REVIEW,
            "agent": state.get("agent", "unknown"),
            "answer": state.get("answer", ""),
        }
    )
    if str(decision) == "approved":
        return {"approval_decision": "approved"}
    return {
        "approval_decision": "rejected",
        "answer": "The drafted answer was rejected by the reviewer.",
        "grounded": False,
        "sources": [],
    }
