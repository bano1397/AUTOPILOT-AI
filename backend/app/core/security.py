"""Security primitives: password hashing and JWT handling.

Pure, settings-driven functions with no HTTP or persistence concerns. Passwords
use argon2id; access/refresh tokens are signed JWTs. Opaque token hashing
(SHA-256) is used to bind a stored refresh-token record to its issued token.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

_password_hasher = PasswordHasher()


# --- Passwords --------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return an argon2id hash of ``password``."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if ``password`` matches ``password_hash``."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        # InvalidHashError subclasses ValueError, not Argon2Error.
        return False


def hash_token(token: str) -> str:
    """Return a SHA-256 hex digest of an opaque token (for DB lookups/binding)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- JWT --------------------------------------------------------------------
class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class TokenData:
    """Decoded JWT claims of interest."""

    subject: str
    token_type: str
    jti: str
    expires_at: datetime
    role: str | None = None


def _encode(
    *, subject: str, token_type: TokenType, expires_delta: timedelta, role: str | None = None
) -> tuple[str, TokenData]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid4())
    payload: dict[str, object] = {
        "sub": subject,
        "type": token_type.value,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if role is not None:
        payload["role"] = role
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, TokenData(
        subject=subject, token_type=token_type.value, jti=jti, expires_at=expires_at, role=role
    )


def create_access_token(*, subject: str, role: str) -> tuple[str, TokenData]:
    """Create a short-lived access token."""
    settings = get_settings()
    return _encode(
        subject=subject,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        role=role,
    )


def create_refresh_token(*, subject: str) -> tuple[str, TokenData]:
    """Create a long-lived refresh token."""
    settings = get_settings()
    return _encode(
        subject=subject,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT, raising :class:`AuthenticationError` on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    try:
        return TokenData(
            subject=payload["sub"],
            token_type=payload["type"],
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            role=payload.get("role"),
        )
    except KeyError as exc:
        raise AuthenticationError("Malformed token") from exc


def access_token_ttl_seconds() -> int:
    """Access-token lifetime in seconds (for the ``expires_in`` response field)."""
    return get_settings().access_token_expire_minutes * 60
