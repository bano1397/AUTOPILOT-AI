"""Singleton registries and the decorators used to populate them.

Importing a module that uses one of these decorators registers the plugin as a
side effect. The :mod:`app.platform.registry.scanner` triggers those imports at
startup so that dropping a new plugin file requires no other code changes.
"""

from __future__ import annotations

from typing import Any

from app.platform.registry.base import ProviderRegistry, Registry

# --- Singleton registries ---------------------------------------------------
agent_registry: Registry[type[Any]] = Registry("agent")
tool_registry: Registry[type[Any]] = Registry("tool")
workflow_registry: Registry[type[Any]] = Registry("workflow")
integration_registry: Registry[type[Any]] = Registry("integration")
provider_registry: ProviderRegistry = ProviderRegistry()


def _resolve_name(target: type[Any], explicit: str | None) -> str:
    """Use an explicit name, else a ``name`` attribute, else the class name."""
    if explicit:
        return explicit
    return str(getattr(target, "name", None) or target.__name__)


def register_agent(
    target: type[Any] | None = None, *, name: str | None = None, **metadata: Any
) -> Any:
    """Class decorator registering an agent. Usable as ``@register_agent`` or with args."""

    def decorate(cls: type[Any]) -> type[Any]:
        agent_registry.register(_resolve_name(cls, name), cls, metadata=metadata)
        return cls

    return decorate(target) if target is not None else decorate


def register_tool(
    target: type[Any] | None = None, *, name: str | None = None, **metadata: Any
) -> Any:
    """Class decorator registering a tool."""

    def decorate(cls: type[Any]) -> type[Any]:
        tool_registry.register(_resolve_name(cls, name), cls, metadata=metadata)
        return cls

    return decorate(target) if target is not None else decorate


def register_workflow(
    target: type[Any] | None = None, *, name: str | None = None, **metadata: Any
) -> Any:
    """Class decorator registering a workflow definition."""

    def decorate(cls: type[Any]) -> type[Any]:
        workflow_registry.register(_resolve_name(cls, name), cls, metadata=metadata)
        return cls

    return decorate(target) if target is not None else decorate


def register_integration(
    target: type[Any] | None = None, *, name: str | None = None, **metadata: Any
) -> Any:
    """Class decorator registering an external integration."""

    def decorate(cls: type[Any]) -> type[Any]:
        integration_registry.register(_resolve_name(cls, name), cls, metadata=metadata)
        return cls

    return decorate(target) if target is not None else decorate


def register_provider(*, kind: str, name: str | None = None, **metadata: Any) -> Any:
    """Class decorator registering a provider under a ``kind`` (llm, embedding, ...)."""

    def decorate(cls: type[Any]) -> type[Any]:
        provider_registry.register(kind, _resolve_name(cls, name), cls, metadata=metadata)
        return cls

    return decorate
