"""Approval use-cases: create pending approvals, list them, decide them.

Deciding an approval resumes the paused workflow run from its checkpoint,
records the finalized exchange to the conversation, and publishes
``ApprovalReceived``. The resume happens *before* the approval is marked
decided, so a resume failure leaves the approval pending (retryable).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.domain.events import ApprovalReceived, ApprovalRequired
from app.domain.interfaces.event_bus import EventBus
from app.features.agents.service import AgentRunService
from app.features.approvals.models import Approval, ApprovalStatus
from app.features.approvals.repository import ApprovalRepository
from app.features.conversations.service import ConversationService

logger = get_logger("app.features.approvals")


class ApprovalService:
    """Owns the approval lifecycle for paused workflow runs."""

    def __init__(
        self,
        session: AsyncSession,
        bus: EventBus,
        agent_service: AgentRunService | None = None,
    ) -> None:
        self._session = session
        self._bus = bus
        self._agents = agent_service
        self._repo = ApprovalRepository(session)
        self._conversations = ConversationService(session)

    async def create_for_run(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        action_type: str,
        payload: dict[str, Any],
    ) -> Approval:
        """Persist a pending approval for an interrupted run and announce it."""
        approval = await self._repo.add(
            Approval(
                run_id=run_id, user_id=user_id, action_type=action_type, payload=payload
            )
        )
        await self._session.commit()
        await self._bus.publish(
            ApprovalRequired(
                run_id=str(run_id), approval_id=str(approval.id), action_type=action_type
            )
        )
        return approval

    async def list_pending(
        self, user_id: UUID, pagination: PaginationParams
    ) -> tuple[Sequence[Approval], int]:
        items = await self._repo.list_pending_for_user(
            user_id, offset=pagination.offset, limit=pagination.limit
        )
        total = await self._repo.count_pending_for_user(user_id)
        return items, total

    async def decide(
        self, user_id: UUID, approval_id: UUID, decision: str
    ) -> tuple[Approval, dict[str, Any]]:
        """Apply the reviewer's decision and finalize the paused run."""
        if self._agents is None:  # pragma: no cover - wiring error
            raise RuntimeError("ApprovalService requires an AgentRunService to decide")

        approval = await self._repo.get(approval_id)
        if approval is None or approval.user_id != user_id:
            # Not-found for foreign approvals too: don't leak existence.
            raise NotFoundError("Approval not found")
        if approval.status is not ApprovalStatus.PENDING:
            raise ConflictError("This approval has already been decided")

        # Resume first: if it fails, the approval stays pending and retryable.
        outcome = await self._agents.resume(approval.run_id, decision)
        state = outcome.state

        approval.status = (
            ApprovalStatus.APPROVED if decision == "approved" else ApprovalStatus.REJECTED
        )
        approval.decided_at = datetime.now(UTC)
        await self._session.commit()

        await self._record_conversation(approval, state, decision)
        await self._bus.publish(
            ApprovalReceived(
                run_id=str(approval.run_id),
                approval_id=str(approval.id),
                decision=decision,
            )
        )
        logger.info(
            "approval.decided",
            extra={"approval_id": str(approval.id), "decision": decision},
        )
        return approval, state

    async def _record_conversation(
        self, approval: Approval, state: dict[str, Any], decision: str
    ) -> None:
        """Record the reviewed exchange to its conversation thread."""
        payload = approval.payload or {}
        conversation_id = payload.get("conversation_id")
        if not conversation_id:
            return
        await self._conversations.record_exchange(
            UUID(str(conversation_id)),
            user_content=str(payload.get("message", "")),
            assistant_content=str(state.get("answer", "")),
            assistant_meta={
                "agent": state.get("agent", "unknown"),
                "model": state.get("model"),
                "grounded": state.get("grounded", False),
                "sources": state.get("sources", []),
                "decision": decision,
            },
        )
