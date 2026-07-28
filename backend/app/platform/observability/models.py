"""AI execution ORM model.

One row per LLM invocation — the audit backbone behind the AI monitoring and
cost dashboards. Rows outlive the requesting user (``SET NULL``) because audit
history must survive account deletion.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class AiExecution(UUIDMixin, TimestampMixin, Base):
    """A single recorded AI (LLM) execution."""

    __tablename__ = "ai_executions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    feature: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Which catalogued prompt produced this call (app.platform.prompts). Nullable
    # because not every call comes from the catalog — and because rows written
    # before the registry existed have no provenance to claim.
    prompt_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Full prompt (JSON-serialized chat messages) and a short response preview.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
