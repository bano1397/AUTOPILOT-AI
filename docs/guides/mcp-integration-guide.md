# MCP Integration Guide

> **Status: planned, not yet implemented.** The approved architecture
> ([`../ARCHITECTURE.md` §8](../ARCHITECTURE.md)) specifies a Model Context
> Protocol layer, but it is **not part of the current build** (milestones
> M1–M5 delivered auth, RAG, agents, workflows/automation, and hardening). This
> guide documents the intended design so it can be added without rework; it
> does not describe shipped functionality.

## Intended design

An `app/mcp/` package with:

- **`clients/`** — connect to external MCP servers (stdio and HTTP/SSE
  transports), enumerate their tools.
- **`tools/`** — an `MCPToolAdapter` that wraps a remote MCP tool in the same
  `Tool` contract native tools use, so agents call MCP tools identically.
- **`registry/`** — load server definitions from config (`mcp_servers.yaml` /
  `MCP_SERVERS`), manage lifecycle/health, and surface remote tools in the tool
  marketplace tagged `origin=mcp`.
- **`servers/`** — expose selected AutoPilot capabilities (RAG query, document
  search, task creation) *as* an MCP server for external MCP clients.

## Why it fits cleanly

Tools are already resolved through the tool registry, and agents select tools
by capability rather than origin — so MCP tools would register alongside native
ones with no agent changes. Security controls mirror the existing model:
explicit server allow-lists, per-tool permissions, and treating all tool output
as untrusted data (never instructions).

## Adding it later

1. Add `mcp` (the official SDK) as a dependency.
2. Implement the client + `MCPToolAdapter`, registering adapted tools via
   `@register_tool`.
3. Add MCP server definitions to config and a startup hook that discovers and
   registers their tools.
4. Optionally expose AutoPilot tools via an MCP server process.

Until then, agents use the native, registry-registered tools described in
[`plugin-development-guide.md`](plugin-development-guide.md).
