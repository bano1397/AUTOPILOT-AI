# Plugin Development Guide

The platform is extended by **registering plugins**, never by editing a central
wiring file. A package scanner imports the plugin packages at startup so their
registration decorators run.

## Providers

A provider implements a domain interface (port) and registers under a `kind`:

```python
# app/infrastructure/llm/openai_provider.py
from app.domain.interfaces.llm import LLMResult
from app.platform.registry import register_provider

@register_provider(kind="llm", name="openai")
class OpenAILLMProvider:
    name = "openai"
    async def chat(self, messages, *, temperature=None, max_tokens=None) -> LLMResult:
        ...
```

Existing kinds: `llm`, `embedding`, `vectorstore`, `database`, `storage`,
`search`, `notification`. Because business logic depends on the interface (not
the class), swapping an implementation is a wiring change in the composition
root (`app/main.py`) — usually driven by a setting.

**Pattern for HTTP-backed providers:** call the service over plain `httpx` with
an injectable `AsyncClient`, so the wire format is unit-testable with
`httpx.MockTransport` (see `infrastructure/search/duckduckgo.py`,
`infrastructure/llm/ollama.py`).

## Registries

| Registry | Decorator | Registers |
|---|---|---|
| agents | `@register_agent` | LangGraph agent nodes |
| tools | `@register_tool` | reusable tools |
| providers | `@register_provider(kind=…)` | external-system implementations |
| workflows | `@register_workflow` | workflow definitions |
| integrations | `@register_integration` | third-party integrations |

Introspect at runtime, e.g. `agent_registry.entries()`. Duplicate or unknown
names fail fast with a clear error.

## Discovery

`app/platform/registry/scanner.py` walks `DEFAULT_PLUGIN_PACKAGES`
(`infrastructure`, `tools`, `agents`, `workflows`, `integrations`) on startup.
Dropping a new module under one of those — with its decorator — is all that is
required; missing packages are skipped, so the platform tolerates partial
builds.
