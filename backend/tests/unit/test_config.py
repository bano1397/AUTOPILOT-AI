"""Unit tests for settings parsing.

Regression: ``CORS_ORIGINS`` arrives as a plain string from the environment or
a ``.env`` file (never JSON). pydantic-settings JSON-decodes list-typed fields
at the source layer unless ``NoDecode`` is applied — without it, every boot
with the documented configuration crashed with a SettingsError.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings

# Settings(_env_file=None) isolates each test from any real .env on the machine.


def test_cors_origins_single_value_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_comma_separated_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "http://localhost:3000, http://localhost:3001 ,https://app.example.com"
    )
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://app.example.com",
    ]


def test_cors_origins_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    # Defaults cover the Next.js dev ports (3000, and 3001 fallback).
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
