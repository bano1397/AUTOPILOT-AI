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


class UploadCapabilities(BaseModel):
    """What this instance will accept for upload.

    Served so the client stops duplicating server rules: the extension list and
    size cap are configuration, and a hardcoded copy in the UI drifts silently
    the moment either changes (image types appear only when OCR is enabled).
    """

    allowed_extensions: list[str]
    max_upload_size_mb: int
    ocr_enabled: bool
