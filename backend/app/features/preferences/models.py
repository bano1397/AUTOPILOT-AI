"""Workspace preference ORM model.

A **single row**: there are no accounts to scope preferences to
(``docs/COMPLETION_PLAN.md`` §3), so this is the one settings record for the whole
instance. The row is created on first read, mirroring how the workspace identity
is provisioned.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class WorkspacePreferences(UUIDMixin, TimestampMixin, Base):
    """Instance-wide preferences that change platform behavior."""

    __tablename__ = "workspace_preferences"

    # UI theme the frontend restores on load ("light" | "dark" | "system").
    theme: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    # Default retrieval breadth when a request doesn't specify top_k.
    default_top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # Whether agent answers go through the approval gate by default.
    require_approval_by_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Master switch for in-app notification creation.
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
