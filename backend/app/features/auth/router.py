"""Authentication HTTP endpoints.

Refresh tokens travel two ways: in the response body (non-browser API clients)
and as an httpOnly cookie scoped to this router's path (browsers — the frontend
never stores the refresh token in JavaScript-readable storage). Refresh/logout
accept either source, preferring the cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.ratelimit import auth_rate_limit
from app.core.schemas import ApiResponse, MessageResponse
from app.features.auth.dependencies import get_auth_service, get_current_user
from app.features.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairRead,
)
from app.features.auth.service import AuthService, IssuedTokens
from app.features.users.models import User
from app.features.users.schemas import UserRead

REFRESH_COOKIE = "autopilot_refresh"
_COOKIE_PATH = "/api/v1/auth"

router = APIRouter()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )


def _resolve_refresh_token(request: Request, payload: RefreshRequest) -> str:
    # An explicit body token beats the ambient cookie: API clients that send a
    # token mean exactly that one (and a replayed old token must not silently
    # succeed via the cookie).
    token = payload.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise AuthenticationError("No refresh token provided")
    return token


def _token_pair(tokens: IssuedTokens) -> ApiResponse[TokenPairRead]:
    return ApiResponse(
        data=TokenPairRead(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
        )
    )


@router.post(
    "/register",
    response_model=ApiResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit())],
)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[UserRead]:
    user = await service.register(payload.email, payload.password)
    return ApiResponse(data=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=ApiResponse[TokenPairRead],
    dependencies=[Depends(auth_rate_limit())],
)
async def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[TokenPairRead]:
    tokens = await service.login(payload.email, payload.password)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_pair(tokens)


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPairRead],
    dependencies=[Depends(auth_rate_limit())],
)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[TokenPairRead]:
    token = _resolve_refresh_token(request, payload or RefreshRequest())
    tokens = await service.refresh(token)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_pair(tokens)


@router.post("/logout", response_model=ApiResponse[MessageResponse])
async def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[MessageResponse]:
    token = (payload or RefreshRequest()).refresh_token or request.cookies.get(
        REFRESH_COOKIE
    )
    if token:
        await service.logout(token)
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
    return ApiResponse(data=MessageResponse(message="Logged out successfully"))


@router.get("/me", response_model=ApiResponse[UserRead])
async def me(current_user: User = Depends(get_current_user)) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(current_user))
