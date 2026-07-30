"""Dependency providers for the agents feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_ai_recorder,
    get_checkpointer,
    get_db_session,
    get_llm,
    get_search,
)
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.search import SearchProvider
from app.features.agents.service import AgentRunService
from app.features.rag.dependencies import get_rag_ask_service
from app.features.rag.service import RagAskService
from app.features.tasks.dependencies import get_task_service
from app.features.tasks.service import TaskService
from app.features.workflows.dependencies import get_workflow_executor
from app.features.workflows.lifecycle import WorkflowLifecycleService
from app.features.workflows.service import WorkflowExecutor
from app.platform.memory import MemoryManager
from app.platform.memory.dependencies import get_memory_manager
from app.platform.observability.recorder import AiExecutionRecorder


def get_agent_run_service(
    llm: LLMProvider = Depends(get_llm),
    recorder: AiExecutionRecorder = Depends(get_ai_recorder),
    ask_service: RagAskService = Depends(get_rag_ask_service),
    executor: WorkflowExecutor = Depends(get_workflow_executor),
    search: SearchProvider = Depends(get_search),
    tasks: TaskService = Depends(get_task_service),
    checkpointer: object | None = Depends(get_checkpointer),
    memory: MemoryManager = Depends(get_memory_manager),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunService:
    return AgentRunService(
        llm,
        recorder,
        ask_service,
        executor,
        search,
        tasks,
        checkpointer,
        memory,
        WorkflowLifecycleService(session),
    )
