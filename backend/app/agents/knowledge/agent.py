"""Knowledge agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.features.rag.schemas import RagMatchRead
from app.features.rag.service import RagAskService
from app.platform.registry import register_agent
from app.workflows.state import AgentState

_TOP_K = 5


@register_agent(supervisor_routable=True)
class KnowledgeAgent(BaseAgent):
    """Answers questions from the user's indexed documents, with citations."""

    name: ClassVar[str] = "knowledge"
    description: ClassVar[str] = (
        "Answers questions from your uploaded documents using retrieval-grounded "
        "generation with citations."
    )

    def __init__(self, ask_service: RagAskService) -> None:
        self._ask = ask_service

    async def run(self, state: AgentState) -> AgentState:
        result = await self._ask.ask(
            UUID(state["user_id"]),
            state.get("request", ""),
            top_k=_TOP_K,
            feature="agent.knowledge",
            agent_name=self.name,
            history=state.get("history", []),
        )
        return {
            "agent": self.name,
            "answer": result.answer,
            "model": result.model,
            "grounded": result.grounded,
            "sources": [
                RagMatchRead.from_chunk(match).model_dump()
                for match in result.matches
            ],
        }
