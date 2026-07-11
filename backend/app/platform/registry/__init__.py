"""Public API for the plugin registry subsystem."""

from app.platform.registry.base import (
    DuplicateRegistrationError,
    PluginNotFoundError,
    ProviderRegistry,
    Registry,
    RegistryEntry,
    RegistryError,
)
from app.platform.registry.registries import (
    agent_registry,
    integration_registry,
    provider_registry,
    register_agent,
    register_integration,
    register_provider,
    register_tool,
    register_workflow,
    tool_registry,
    workflow_registry,
)
from app.platform.registry.scanner import DEFAULT_PLUGIN_PACKAGES, discover_plugins

__all__ = [
    "DEFAULT_PLUGIN_PACKAGES",
    "DuplicateRegistrationError",
    "PluginNotFoundError",
    "ProviderRegistry",
    "Registry",
    "RegistryEntry",
    "RegistryError",
    "agent_registry",
    "discover_plugins",
    "integration_registry",
    "provider_registry",
    "register_agent",
    "register_integration",
    "register_provider",
    "register_tool",
    "register_workflow",
    "tool_registry",
    "workflow_registry",
]
