"""Request/response schemas for the approvals feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.approvals.models import ApprovalStatus
from app.features.rag.schemas import RagMatchRead


class ApprovalRead(BaseModel):
    """An approval request."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    action_type: str
    status: ApprovalStatus
    payload: dict[str, Any] | None
    created_at: datetime
    decided_at: datetime | None


class ApprovalDecisionRequest(BaseModel):
    """The reviewer's decision."""

    decision: Literal["approved", "rejected"]


class ApprovalDecisionRead(BaseModel):
    """Outcome of deciding an approval: the finalized answer."""

    approval: ApprovalRead
    answer: str
    agent: str
    grounded: bool
    model: str | None
    sources: list[RagMatchRead]
