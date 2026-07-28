"""Workspace identity ORM model.

With authentication removed (``docs/COMPLETION_PLAN.md`` §3) this table holds
the single shared workspace identity rather than a set of accounts. It keeps its
own row so every feature's ``user_id`` foreign key and vector-metadata filter
still has a stable subject to point at. There is deliberately no password hash
and no role: nothing authenticates, and nothing authorizes.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """The workspace identity every request runs as."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id!r} email={self.email!r}>"
