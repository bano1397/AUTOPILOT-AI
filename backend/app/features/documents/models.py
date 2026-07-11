"""Document ORM model."""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin


class DocumentStatus(str, enum.Enum):
    """Lifecycle of an uploaded document (blueprint §23.2).

    ``UPLOADED`` → ``PROCESSING`` → ``INDEXED`` | ``FAILED``. This feature
    creates documents as ``UPLOADED``; the ingestion pipeline advances them.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(UUIDMixin, TimestampMixin, Base):
    """A user-owned uploaded file tracked through the ingestion lifecycle."""

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Original client filename, kept for display only — never used on disk.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Canonical MIME type derived from the validated extension (not client-claimed).
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    # Opaque StorageProvider key; only the provider may interpret it.
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # ``metadata`` is reserved by SQLAlchemy's declarative API, hence the attribute name.
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Document id={self.id!r} filename={self.filename!r} status={self.status.value!r}>"


class DocumentChunk(UUIDMixin, TimestampMixin, Base):
    """One chunk of an ingested document (blueprint ERD).

    The database keeps a preview for display/citation; the vector store holds
    the full chunk text. ``vector_id`` links the two (filled by the indexing
    stage; NULL until then).
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_preview: Mapped[str] = mapped_column(String(500), nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<DocumentChunk document_id={self.document_id!r} index={self.chunk_index!r}>"
