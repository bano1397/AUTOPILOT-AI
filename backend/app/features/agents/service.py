"""Agent-run use-cases: assemble the supervisor graph and execute it."""

from __future__ import annotations

import json
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
from app.features.workflows.lifecycle import (
    DEFAULT_WORKFLOW_NAME,
    WorkflowLifecycleService,
)
from app.features.workflows.service import ExecutionOutcome, WorkflowExecutor
from app.platform.memory import MemoryManager
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import agent_registry
from app.workflows.graph import build_agent_graph
from app.workflows.spec import GraphSpec
from app.workflows.state import AgentState

logger = get_logger("app.features.agents")

WORKFLOW_NAME = DEFAULT_WORKFLOW_NAME


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
        memory: MemoryManager | None = None,
        lifecycle: WorkflowLifecycleService | None = None,
    ) -> None:
        self._supervisor = SupervisorAgent(llm, recorder)
        knowledge = KnowledgeAgent(ask_service)
        general = GeneralAgent(llm, recorder, memory)
        research = ResearchAgent(search, llm, recorder)
        planner = PlannerAgent(tasks, llm, recorder)
        self._agents = {
            knowledge.name: knowledge,
            general.name: general,
            research.name: research,
            planner.name: planner,
        }
        self._checkpointer = checkpointer
        self._executor = executor
        self._lifecycle = lifecycle
        # Compiled graphs are cached by spec so an unchanged version is built
        # once per process rather than once per request. Compilation is pure
        # in-memory work, but it is not free and it is trivially cacheable.
        self._graphs: dict[str, Any] = {}

    def _graph_for(self, spec: GraphSpec | None) -> Any:
        key = json.dumps(spec.to_mapping(), sort_keys=True) if spec else "__default__"
        cached = self._graphs.get(key)
        if cached is None:
            cached = build_agent_graph(
                self._supervisor,
                self._agents,
                checkpointer=self._checkpointer,
                spec=spec,
            )
            self._graphs[key] = cached
        return cached

    async def run(
        self,
        user_id: UUID,
        message: str,
        history: list[dict[str, str]] | None = None,
        *,
        require_approval: bool = False,
    ) -> ExecutionOutcome:
        """Execute the active version of the supervisor workflow as a run.

        With ``require_approval`` the run pauses at the approval gate and the
        outcome reports ``interrupted=True`` with the draft in its state — but
        only if the active version includes the gate at all.
        """
        version_id: UUID | None = None
        spec: GraphSpec | None = None
        if self._lifecycle is not None:
            version, spec = await self._lifecycle.active_spec(WORKFLOW_NAME)
            version_id = version.id

        initial: AgentState = {
            "user_id": str(user_id),
            "request": message,
            "history": history or [],
            "needs_approval": require_approval,
        }
        outcome = await self._executor.execute(
            user_id=user_id,
            workflow_name=WORKFLOW_NAME,
            graph=self._graph_for(spec),
            initial_state=initial,
            input_payload={
                "message": message[:500],
                "history_turns": len(history or []),
            },
            output_builder=_summarize_output,
            workflow_version_id=version_id,
        )
        logger.info(
            "agents.run_completed",
            extra={
                "run_id": str(outcome.run_id),
                "agent": outcome.state.get("agent", "unknown"),
                "interrupted": outcome.interrupted,
                "version_id": str(version_id) if version_id else None,
            },
        )
        return outcome

    async def resume(self, run_id: UUID, decision: str) -> ExecutionOutcome:
        """Resume a run paused at the approval gate with the given decision.

        Resumes under the version the run *pinned*, not whichever is active
        now: activating a new version between pause and approval must not
        change the graph a half-finished run is being replayed into. Its
        checkpoint holds node names from the original spec, and resuming into
        a different topology would at best rewrite history and at worst fail
        to find the node it paused on.
        """
        spec = await self._spec_for_run(run_id)
        return await self._executor.resume(
            run_id=run_id,
            graph=self._graph_for(spec),
            resume_value=decision,
            output_builder=_summarize_output,
        )

    async def _spec_for_run(self, run_id: UUID) -> GraphSpec | None:
        if self._lifecycle is None:
            return None
        version_id = await self._executor.version_id_for_run(run_id)
        if version_id is None:
            # A run from before versioning, or one executed without a
            # lifecycle service. The default graph is what produced it.
            return None
        version = await self._lifecycle.get_version(version_id)
        return GraphSpec.from_mapping(version.graph_spec)


def list_registered_agents() -> list[tuple[str, str]]:
    """Return (name, description) for every agent in the registry."""
    return [
        (entry.name, str(getattr(entry.target, "description", "")))
        for entry in agent_registry.entries()
    ]
