"""Agent-run use-cases: assemble the supervisor graph and execute it."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.agents.general.agent import GeneralAgent
from app.agents.knowledge.agent import KnowledgeAgent
from app.agents.planner.agent import PlannerAgent
from app.agents.research.agent import ResearchAgent
from app.agents.supervisor.supervisor import SupervisorAgent
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.search import SearchProvider
from app.features.rag.service import RagAskService
from app.features.tasks.service import TaskService
from app.features.workflows.service import ExecutionOutcome, WorkflowExecutor
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import agent_registry
from app.workflows.graph import build_agent_graph
from app.workflows.state import AgentState

logger = get_logger("app.features.agents")

WORKFLOW_NAME = "agents.ask"


def _summarize_output(state: dict[str, Any]) -> dict[str, Any]:
    """Compact run-output summary stored on the workflow run row."""
    return {
        "agent": state.get("agent"),
        "grounded": state.get("grounded", False),
        "model": state.get("model"),
        "answer_preview": str(state.get("answer", ""))[:500],
        "source_count": len(state.get("sources", [])),
    }


class AgentRunService:
    """Runs a user request through the supervisor graph as a workflow run."""

    def __init__(
        self,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
        ask_service: RagAskService,
        executor: WorkflowExecutor,
        search: SearchProvider,
        tasks: TaskService,
        checkpointer: Any | None = None,
    ) -> None:
        supervisor = SupervisorAgent(llm, recorder)
        knowledge = KnowledgeAgent(ask_service)
        general = GeneralAgent(llm, recorder)
        research = ResearchAgent(search, llm, recorder)
        planner = PlannerAgent(tasks, llm, recorder)
        self._graph = build_agent_graph(
            supervisor,
            {
                knowledge.name: knowledge,
                general.name: general,
                research.name: research,
                planner.name: planner,
            },
            checkpointer=checkpointer,
        )
        self._executor = executor

    async def run(
        self,
        user_id: UUID,
        message: str,
        history: list[dict[str, str]] | None = None,
        *,
        require_approval: bool = False,
    ) -> ExecutionOutcome:
        """Execute the graph as a persistent run.

        With ``require_approval`` the run pauses at the approval gate and the
        outcome reports ``interrupted=True`` with the draft in its state.
        """
        initial: AgentState = {
            "user_id": str(user_id),
            "request": message,
            "history": history or [],
            "needs_approval": require_approval,
        }
        outcome = await self._executor.execute(
            user_id=user_id,
            workflow_name=WORKFLOW_NAME,
            graph=self._graph,
            initial_state=initial,
            input_payload={
                "message": message[:500],
                "history_turns": len(history or []),
            },
            output_builder=_summarize_output,
        )
        logger.info(
            "agents.run_completed",
            extra={
                "run_id": str(outcome.run_id),
                "agent": outcome.state.get("agent", "unknown"),
                "interrupted": outcome.interrupted,
            },
        )
        return outcome

    async def resume(self, run_id: UUID, decision: str) -> ExecutionOutcome:
        """Resume a run paused at the approval gate with the given decision."""
        return await self._executor.resume(
            run_id=run_id,
            graph=self._graph,
            resume_value=decision,
            output_builder=_summarize_output,
        )


def list_registered_agents() -> list[tuple[str, str]]:
    """Return (name, description) for every agent in the registry."""
    return [
        (entry.name, str(getattr(entry.target, "description", "")))
        for entry in agent_registry.entries()
    ]
