"""Supervisor agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.supervisor.prompts import build_routing_messages
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProvider
from app.platform.observability.recorder import AiExecutionRecorder
from app.workflows.state import AgentState

logger = get_logger("app.agents.supervisor")

ROUTE_KNOWLEDGE = "knowledge"
ROUTE_GENERAL = "general"
ROUTE_RESEARCH = "research"
ROUTE_PLANNER = "planner"


def parse_route(reply: str) -> str:
    """Map the classifier's reply to a route.

    Fail-safe toward ``knowledge``: mis-routing a chat message to RAG yields an
    honest "nothing found" answer, while mis-routing a document question to the
    general agent risks an ungrounded (hallucinated) answer.
    """
    normalized = reply.strip().lower()
    if ROUTE_RESEARCH in normalized:
        return ROUTE_RESEARCH
    if "plan" in normalized:  # the classifier answers "plan"; the agent is "planner"
        return ROUTE_PLANNER
    if ROUTE_GENERAL in normalized:
        return ROUTE_GENERAL
    return ROUTE_KNOWLEDGE


def fast_route(request: str) -> str | None:
    """Deterministic routing for explicit commands, skipping the classifier.

    Small local models occasionally mis-classify even explicit requests (seen
    live with llama3.2 routing "Research ..." to knowledge). Unambiguous
    command verbs don't need an LLM opinion — this is both more reliable and
    one LLM call cheaper. Everything else still goes to the classifier.
    """
    normalized = request.strip().lower()
    if normalized.startswith(("research ", "look up ")) or "search the web" in normalized:
        return ROUTE_RESEARCH
    if normalized.startswith(("plan ", "break down ")):
        return ROUTE_PLANNER
    return None


class SupervisorAgent(BaseAgent):
    """Classifies the request and selects the worker agent."""

    name: ClassVar[str] = "supervisor"
    description: ClassVar[str] = "Routes each request to the right specialist agent."

    def __init__(self, llm: LLMProvider, recorder: AiExecutionRecorder) -> None:
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        request = state.get("request", "")
        user_id = state.get("user_id")

        direct = fast_route(request)
        if direct is not None:
            logger.info("supervisor.fast_routed", extra={"route": direct})
            return {"route": direct}

        result = await self._recorder.chat(
            self._llm,
            build_routing_messages(request),
            feature="agent.supervisor",
            agent_name=self.name,
            user_id=UUID(user_id) if user_id else None,
            temperature=0.0,
            prompt_key="agent.supervisor.routing",
            prompt_version=1,
        )
        route = parse_route(result.content)
        logger.info("supervisor.routed", extra={"route": route})
        return {"route": route}
