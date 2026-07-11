"""Request/response schemas for the auth feature."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Refresh/logout payload.

    The token may instead arrive via the httpOnly auth cookie (preferred for
    browsers); the body field remains for non-browser API clients.
    """

    refresh_token: str | None = Field(default=None, min_length=1)


class TokenPairRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
