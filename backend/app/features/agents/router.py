"""Agents HTTP endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.schemas import ApiResponse
from app.features.agents.dependencies import get_agent_run_service
from app.features.agents.schemas import (
    AgentAskRead,
    AgentAskRequest,
    AgentInfoRead,
    WebSourceRead,
)
from app.features.agents.service import AgentRunService, list_registered_agents
from app.features.approvals.dependencies import get_approval_service
from app.features.approvals.service import ApprovalService
from app.features.conversations.dependencies import get_conversation_service
from app.features.conversations.service import ConversationService
from app.features.preferences.dependencies import get_preferences_service
from app.features.preferences.service import PreferencesService
from app.features.rag.schemas import RagMatchRead
from app.features.users.dependencies import get_workspace_user
from app.features.users.models import User
from app.workflows.nodes import APPROVAL_ACTION_ANSWER_REVIEW

router = APIRouter()


@router.get("", response_model=ApiResponse[list[AgentInfoRead]])
async def list_agents(
    _: User = Depends(get_workspace_user),
) -> ApiResponse[list[AgentInfoRead]]:
    return ApiResponse(
        data=[
            AgentInfoRead(name=name, description=description)
            for name, description in list_registered_agents()
        ]
    )


def _sources(state: dict[str, Any]) -> list[RagMatchRead]:
    return [RagMatchRead.model_validate(source) for source in state.get("sources", [])]


def _web_sources(state: dict[str, Any]) -> list[WebSourceRead]:
    return [
        WebSourceRead.model_validate(source)
        for source in state.get("web_sources", [])
    ]


@router.post("/ask", response_model=ApiResponse[AgentAskRead])
async def ask_agents(
    payload: AgentAskRequest,
    workspace_user: User = Depends(get_workspace_user),
    service: AgentRunService = Depends(get_agent_run_service),
    conversations: ConversationService = Depends(get_conversation_service),
    approvals: ApprovalService = Depends(get_approval_service),
    preferences: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[AgentAskRead]:
    # An omitted require_approval defers to the workspace preference.
    require_approval = payload.require_approval
    if require_approval is None:
        require_approval = (await preferences.get()).require_approval_by_default

    # Resolve the thread and collect prior turns BEFORE recording this one.
    conversation = await conversations.resolve(
        workspace_user.id, payload.conversation_id, payload.message
    )
    history = await conversations.history(conversation.id)

    outcome = await service.run(
        workspace_user.id,
        payload.message,
        history,
        require_approval=require_approval,
    )
    state: dict[str, Any] = dict(outcome.state)
    answer = str(state.get("answer", ""))

    if outcome.interrupted:
        # Draft paused for review: nothing is committed to the conversation
        # until the reviewer decides.
        approval = await approvals.create_for_run(
            workspace_user.id,
            outcome.run_id,
            action_type=APPROVAL_ACTION_ANSWER_REVIEW,
            payload={
                "message": payload.message,
                "conversation_id": str(conversation.id),
                "draft_answer": answer,
                "agent": state.get("agent", "unknown"),
                "grounded": state.get("grounded", False),
                "model": state.get("model"),
                "sources": state.get("sources", []),
                "web_sources": state.get("web_sources", []),
            },
        )
        return ApiResponse(
            data=AgentAskRead(
                conversation_id=conversation.id,
                run_id=outcome.run_id,
                status="awaiting_approval",
                approval_id=approval.id,
                message=payload.message,
                answer=answer,
                agent=str(state.get("agent", "unknown")),
                grounded=bool(state.get("grounded", False)),
                model=state.get("model"),
                sources=_sources(state),
                web_sources=_web_sources(state),
            )
        )

    await conversations.record_exchange(
        conversation.id,
        user_content=payload.message,
        assistant_content=answer,
        assistant_meta={
            "agent": state.get("agent", "unknown"),
            "model": state.get("model"),
            "grounded": state.get("grounded", False),
            "sources": state.get("sources", []),
            "web_sources": state.get("web_sources", []),
        },
    )
    return ApiResponse(
        data=AgentAskRead(
            conversation_id=conversation.id,
            run_id=outcome.run_id,
            status="completed",
            message=payload.message,
            answer=answer,
            agent=str(state.get("agent", "unknown")),
            grounded=bool(state.get("grounded", False)),
            model=state.get("model"),
            sources=_sources(state),
            web_sources=_web_sources(state),
        )
    )
