"""Tests for plugin discovery."""

from __future__ import annotations

from app.platform.registry import discover_plugins


def test_absent_package_is_tolerated() -> None:
    # Packages created later in the roadmap must not break discovery today.
    assert discover_plugins(["app.package_does_not_exist"]) == 0


def test_discovers_submodules_of_existing_package() -> None:
    # The system feature has at least ``router`` and ``schemas`` submodules.
    imported = discover_plugins(["app.features.system"])

    assert imported >= 2
