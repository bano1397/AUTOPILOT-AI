"""General agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.general.prompts import (
    GENERAL_PROMPT_KEY,
    GENERAL_PROMPT_VERSION,
    build_general_messages,
)
from app.domain.interfaces.llm import LLMProvider
from app.platform.memory import MemoryManager
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent
from app.workflows.state import AgentState

_MEMORY_RECALL_LIMIT = 3


@register_agent(supervisor_routable=True)
class GeneralAgent(BaseAgent):
    """Handles requests that do not concern the user's documents."""

    name: ClassVar[str] = "general"
    description: ClassVar[str] = (
        "Handles greetings and general questions that don't involve your documents."
    )

    def __init__(
        self,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
        memory: MemoryManager | None = None,
    ) -> None:
        self._llm = llm
        self._recorder = recorder
        self._memory = memory

    async def run(self, state: AgentState) -> AgentState:
        user_id = state.get("user_id")
        request = state.get("request", "")
        parsed_user_id = UUID(user_id) if user_id else None

        # Durable facts are an enhancement, not the answer: recall degrades to
        # nothing rather than failing the reply when the vector store is down.
        memories: list[str] = []
        if self._memory is not None and parsed_user_id is not None:
            recollections = await self._memory.recall_or_empty(
                parsed_user_id, request, top_k=_MEMORY_RECALL_LIMIT
            )
            memories = [item.entry.content for item in recollections]

        result = await self._recorder.chat(
            self._llm,
            build_general_messages(request, state.get("history", []), memories),
            feature="agent.general",
            agent_name=self.name,
            user_id=parsed_user_id,
            temperature=0.7,
            prompt_key=GENERAL_PROMPT_KEY,
            prompt_version=GENERAL_PROMPT_VERSION,
        )
        return {
            "agent": self.name,
            "answer": result.content,
            "model": result.model,
            "grounded": False,
            "sources": [],
        }
