"""General agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.general.prompts import build_general_messages
from app.domain.interfaces.llm import LLMProvider
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent
from app.workflows.state import AgentState


@register_agent
class GeneralAgent(BaseAgent):
    """Handles requests that do not concern the user's documents."""

    name: ClassVar[str] = "general"
    description: ClassVar[str] = (
        "Handles greetings and general questions that don't involve your documents."
    )

    def __init__(self, llm: LLMProvider, recorder: AiExecutionRecorder) -> None:
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        user_id = state.get("user_id")
        result = await self._recorder.chat(
            self._llm,
            build_general_messages(state.get("request", ""), state.get("history", [])),
            feature="agent.general",
            agent_name=self.name,
            user_id=UUID(user_id) if user_id else None,
            temperature=0.7,
            prompt_key="agent.general.system",
            prompt_version=1,
        )
        return {
            "agent": self.name,
            "answer": result.content,
            "model": result.model,
            "grounded": False,
            "sources": [],
        }
