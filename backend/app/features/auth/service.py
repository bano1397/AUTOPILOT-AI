"""Authentication use-cases.

The service owns the transaction boundary and coordinates its repositories. It
raises domain errors (:mod:`app.core.exceptions`) that the centralized handlers
translate into HTTP responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    TokenType,
    access_token_ttl_seconds,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.features.auth.models import RefreshToken
from app.features.auth.repository import RefreshTokenRepository
from app.features.users.models import User
from app.features.users.repository import UserRepository


@dataclass(frozen=True)
class IssuedTokens:
    """A freshly issued access/refresh token pair."""

    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    """Registration, authentication, and token lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)

    async def register(self, email: str, password: str) -> User:
        if await self._users.email_exists(email):
            raise ConflictError("An account with this email already exists")
        user = User(email=email, password_hash=hash_password(password))
        await self._users.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is inactive")
        return user

    async def login(self, email: str, password: str) -> IssuedTokens:
        user = await self.authenticate(email, password)
        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        data = decode_token(refresh_token)
        if data.token_type != TokenType.REFRESH.value:
            raise AuthenticationError("Invalid token type")

        record = await self._tokens.get_by_jti(data.jti)
        if record is None or record.revoked:
            raise AuthenticationError("Refresh token is no longer valid")
        if record.token_hash != hash_token(refresh_token):
            raise AuthenticationError("Refresh token mismatch")

        user = await self._users.get_by_id(UUID(data.subject))
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Rotate: revoke the presented token, then issue a new pair.
        await self._tokens.revoke(record)
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        try:
            data = decode_token(refresh_token)
        except AuthenticationError:
            return  # logout is idempotent for invalid tokens
        record = await self._tokens.get_by_jti(data.jti)
        if record is not None and not record.revoked:
            await self._tokens.revoke(record)
            await self._session.commit()

    async def _issue_tokens(self, user: User) -> IssuedTokens:
        access_token, _ = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token, refresh_data = create_refresh_token(subject=str(user.id))
        await self._tokens.add(
            RefreshToken(
                user_id=user.id,
                jti=refresh_data.jti,
                token_hash=hash_token(refresh_token),
                expires_at=refresh_data.expires_at,
            )
        )
        await self._session.commit()
        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=access_token_ttl_seconds(),
        )
