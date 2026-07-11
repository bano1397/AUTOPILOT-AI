"""Dependency providers for the approvals feature."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, get_event_bus
from app.domain.interfaces.event_bus import EventBus
from app.features.agents.dependencies import get_agent_run_service
from app.features.agents.service import AgentRunService
from app.features.approvals.service import ApprovalService


def get_approval_service(
    session: AsyncSession = Depends(get_db_session),
    bus: EventBus = Depends(get_event_bus),
    agent_service: AgentRunService = Depends(get_agent_run_service),
) -> ApprovalService:
    return ApprovalService(session, bus, agent_service)
