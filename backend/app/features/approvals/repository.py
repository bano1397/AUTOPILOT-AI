"""Data-access repository for approvals."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.approvals.models import Approval, ApprovalStatus


class ApprovalRepository:
    """Persistence operations for :class:`Approval`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, approval: Approval) -> Approval:
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def get(self, approval_id: UUID) -> Approval | None:
        return await self._session.get(Approval, approval_id)

    async def list_pending_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> Sequence[Approval]:
        result = await self._session.execute(
            select(Approval)
            .where(Approval.user_id == user_id, Approval.status == ApprovalStatus.PENDING)
            .order_by(Approval.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_pending_for_user(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Approval)
            .where(Approval.user_id == user_id, Approval.status == ApprovalStatus.PENDING)
        )
        return int(result.scalar_one())
