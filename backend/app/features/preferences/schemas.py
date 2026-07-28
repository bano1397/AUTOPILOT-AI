"""Request/response schemas for workspace preferences."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Theme = Literal["light", "dark", "system"]


class PreferencesRead(BaseModel):
    """Current instance-wide preferences."""

    model_config = ConfigDict(from_attributes=True)

    theme: Theme
    default_top_k: int
    require_approval_by_default: bool
    notifications_enabled: bool


class PreferencesUpdateRequest(BaseModel):
    """Partial update; omitted fields keep their current value."""

    theme: Theme | None = None
    default_top_k: int | None = Field(default=None, ge=1, le=20)
    require_approval_by_default: bool | None = None
    notifications_enabled: bool | None = None
