"""Response schemas for the documents feature."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.documents.models import DocumentStatus


class DocumentRead(BaseModel):
    """Public representation of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    metadata: dict[str, Any] = Field(validation_alias="doc_metadata")
    created_at: datetime
