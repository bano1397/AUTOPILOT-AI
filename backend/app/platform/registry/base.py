"""Generic plugin registry and factory.

A :class:`Registry` maps a unique name to a registered target (typically a class)
plus optional metadata, and can instantiate it on demand (factory). This is the
mechanism behind the platform's Open/Closed extensibility: capabilities are added
by registering new plugins, never by modifying existing code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.core.logging import get_logger

logger = get_logger("app.registry")

T = TypeVar("T")


class RegistryError(Exception):
    """Base class for registry errors."""


class DuplicateRegistrationError(RegistryError):
    """Raised when a name is registered more than once without ``override``."""


class PluginNotFoundError(RegistryError):
    """Raised when a requested plugin name is not registered."""


@dataclass(frozen=True)
class RegistryEntry(Generic[T]):
    """A single registered plugin and its metadata."""

    name: str
    target: T
    metadata: dict[str, Any] = field(default_factory=dict)


class Registry(Generic[T]):
    """A named collection of plugins of a single kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._entries: dict[str, RegistryEntry[T]] = {}

    @property
    def kind(self) -> str:
        return self._kind

    def register(
        self,
        name: str,
        target: T,
        *,
        metadata: dict[str, Any] | None = None,
        override: bool = False,
    ) -> T:
        """Register ``target`` under ``name``. Fails fast on empty or duplicate names."""
        if not name:
            raise RegistryError(f"{self._kind} plugin name must be non-empty")
        if name in self._entries and not override:
            raise DuplicateRegistrationError(
                f"{self._kind} plugin '{name}' is already registered"
            )
        self._entries[name] = RegistryEntry(name=name, target=target, metadata=metadata or {})
        logger.debug("plugin_registered", extra={"kind": self._kind, "name": name})
        return target

    def get(self, name: str) -> T:
        """Return the registered target for ``name`` or raise :class:`PluginNotFoundError`."""
        entry = self._entries.get(name)
        if entry is None:
            raise PluginNotFoundError(
                f"{self._kind} plugin '{name}' is not registered. "
                f"Available: {self.names()}"
            )
        return entry.target

    def get_entry(self, name: str) -> RegistryEntry[T]:
        """Return the full registry entry (target + metadata) for ``name``."""
        entry = self._entries.get(name)
        if entry is None:
            raise PluginNotFoundError(f"{self._kind} plugin '{name}' is not registered")
        return entry

    def create(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Instantiate the plugin registered under ``name`` (factory)."""
        target = self.get(name)
        if not callable(target):
            raise RegistryError(
                f"{self._kind} plugin '{name}' is not callable and cannot be instantiated"
            )
        return target(*args, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._entries)

    def entries(self) -> list[RegistryEntry[T]]:
        return list(self._entries.values())

    def clear(self) -> None:
        """Remove all registrations (primarily for tests)."""
        self._entries.clear()

    def __contains__(self, name: object) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)


class ProviderRegistry:
    """Registry of external providers, partitioned by ``kind`` (llm, embedding, ...)."""

    def __init__(self) -> None:
        self._by_kind: dict[str, Registry[Any]] = {}

    def _registry(self, kind: str) -> Registry[Any]:
        return self._by_kind.setdefault(kind, Registry(f"provider:{kind}"))

    def register(
        self,
        kind: str,
        name: str,
        target: Any,
        *,
        metadata: dict[str, Any] | None = None,
        override: bool = False,
    ) -> Any:
        return self._registry(kind).register(
            name, target, metadata=metadata, override=override
        )

    def get(self, kind: str, name: str) -> Any:
        return self._registry(kind).get(name)

    def create(self, kind: str, name: str, *args: Any, **kwargs: Any) -> Any:
        return self._registry(kind).create(name, *args, **kwargs)

    def kinds(self) -> list[str]:
        return sorted(self._by_kind)

    def names(self, kind: str) -> list[str]:
        return self._registry(kind).names()

    def clear(self) -> None:
        self._by_kind.clear()
