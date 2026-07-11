"""Unit tests for password hashing and JWT handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-password")

    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_handles_invalid_hash() -> None:
    assert verify_password("anything", "not-a-valid-hash") is False


def test_hash_token_is_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")


def test_access_token_roundtrip() -> None:
    token, data = create_access_token(subject="user-1", role="admin")
    decoded = decode_token(token)

    assert decoded.subject == "user-1"
    assert decoded.role == "admin"
    assert decoded.token_type == TokenType.ACCESS.value
    assert decoded.jti == data.jti


def test_refresh_token_has_refresh_type() -> None:
    token, _ = create_refresh_token(subject="user-2")
    assert decode_token(token).token_type == TokenType.REFRESH.value


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(AuthenticationError):
        decode_token("clearly.not.a.jwt")


def test_decode_expired_token_raises() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "user-3",
            "type": "access",
            "jti": "j1",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthenticationError):
        decode_token(expired)
