"""Workspace preference HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.schemas import ApiResponse
from app.features.preferences.dependencies import get_preferences_service
from app.features.preferences.schemas import PreferencesRead, PreferencesUpdateRequest
from app.features.preferences.service import PreferencesService

router = APIRouter()


@router.get("", response_model=ApiResponse[PreferencesRead])
async def get_preferences(
    service: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[PreferencesRead]:
    preferences = await service.get()
    return ApiResponse(data=PreferencesRead.model_validate(preferences))


@router.patch("", response_model=ApiResponse[PreferencesRead])
async def update_preferences(
    payload: PreferencesUpdateRequest,
    service: PreferencesService = Depends(get_preferences_service),
) -> ApiResponse[PreferencesRead]:
    preferences = await service.update(payload)
    return ApiResponse(data=PreferencesRead.model_validate(preferences))
