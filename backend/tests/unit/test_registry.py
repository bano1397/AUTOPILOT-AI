"""Tests for the plugin registry, provider registry, and decorators."""

from __future__ import annotations

import pytest
from app.platform.registry import (
    DuplicateRegistrationError,
    PluginNotFoundError,
    ProviderRegistry,
    Registry,
    provider_registry,
    register_provider,
)


class _Dummy:
    def __init__(self, value: int = 1) -> None:
        self.value = value


def test_register_and_get() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")
    registry.register("dummy", _Dummy)

    assert registry.get("dummy") is _Dummy
    assert "dummy" in registry
    assert registry.names() == ["dummy"]
    assert len(registry) == 1


def test_register_with_metadata_is_retrievable() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")
    registry.register("dummy", _Dummy, metadata={"category": "test"})

    assert registry.get_entry("dummy").metadata == {"category": "test"}


def test_duplicate_registration_raises() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")
    registry.register("dummy", _Dummy)

    with pytest.raises(DuplicateRegistrationError):
        registry.register("dummy", _Dummy)


def test_override_allows_reregistration() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")
    registry.register("dummy", _Dummy)
    registry.register("dummy", _Dummy, override=True)  # must not raise

    assert len(registry) == 1


def test_get_unknown_raises() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")

    with pytest.raises(PluginNotFoundError):
        registry.get("missing")


def test_create_instantiates_target() -> None:
    registry: Registry[type[_Dummy]] = Registry("thing")
    registry.register("dummy", _Dummy)

    instance = registry.create("dummy", value=42)

    assert isinstance(instance, _Dummy)
    assert instance.value == 42


def test_provider_registry_partitions_by_kind() -> None:
    providers = ProviderRegistry()
    providers.register("llm", "ollama", _Dummy)
    providers.register("embedding", "ollama", _Dummy)

    assert providers.get("llm", "ollama") is _Dummy
    assert providers.kinds() == ["embedding", "llm"]
    assert providers.names("llm") == ["ollama"]


def test_register_provider_decorator_populates_global_registry() -> None:
    @register_provider(kind="test_kind", name="sample", category="unit")
    class SampleProvider:
        pass

    assert provider_registry.get("test_kind", "sample") is SampleProvider
