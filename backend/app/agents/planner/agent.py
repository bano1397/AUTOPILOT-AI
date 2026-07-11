"""Planner agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.planner.parsing import parse_plan
from app.agents.planner.prompts import build_planner_messages
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProvider
from app.features.tasks.service import TaskService
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent
from app.workflows.state import AgentState

logger = get_logger("app.agents.planner")

UNPARSEABLE_ANSWER = (
    "I couldn't turn that into a structured task list, so nothing was saved. "
    "Here is the raw suggestion:\n\n"
)


@register_agent
class PlannerAgent(BaseAgent):
    """Turns a goal into persisted, prioritized tasks."""

    name: ClassVar[str] = "planner"
    description: ClassVar[str] = (
        "Breaks a goal into concrete, prioritized tasks and saves them to your "
        "task list."
    )

    def __init__(
        self,
        tasks: TaskService,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
    ) -> None:
        self._tasks = tasks
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        user_id = UUID(state["user_id"])
        result = await self._recorder.chat(
            self._llm,
            build_planner_messages(state.get("request", ""), state.get("history", [])),
            feature="agent.planner",
            agent_name=self.name,
            user_id=user_id,
            temperature=0.2,
        )

        items = parse_plan(result.content)
        if not items:
            # Honest failure: nothing persisted, the raw suggestion is shown.
            logger.warning("planner.unparseable_plan")
            return {
                "agent": self.name,
                "answer": UNPARSEABLE_ANSWER + result.content,
                "model": result.model,
                "grounded": False,
                "sources": [],
                "web_sources": [],
            }

        created = await self._tasks.create_planned(
            user_id, [(item.title, item.description, item.priority) for item in items]
        )
        lines = "\n".join(
            f"- [{task.priority.value}] {task.title}" for task in created
        )
        return {
            "agent": self.name,
            "answer": (
                f"I created {len(created)} task(s) on your task list:\n{lines}"
            ),
            "model": result.model,
            "grounded": False,
            "sources": [],
            "web_sources": [],
        }
