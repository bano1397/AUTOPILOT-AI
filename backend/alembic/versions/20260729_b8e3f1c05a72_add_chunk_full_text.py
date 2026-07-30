"""add full chunk text for keyword search

Hybrid retrieval (blueprint §17) scores chunk text with BM25, which needs the
text in the database — the vector store's copy is not portably searchable.

Nullable with no backfill, deliberately: the text is only in the vector store,
and a migration that reached out to Chroma or Qdrant would couple schema
migration to a network service and fail closed on any deployment where that
service is briefly unavailable. Documents indexed before this migration stay
vector-searchable and become keyword-searchable after
``POST /documents/{id}/reindex``, which rebuilds them from the stored file.

Revision ID: b8e3f1c05a72
Revises: a4d90c17e6b2
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e3f1c05a72"
down_revision: str | None = "a4d90c17e6b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks", sa.Column("content", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "content")
