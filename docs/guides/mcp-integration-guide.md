# MCP Integration Guide

> **Status: implemented.** `app/mcp/` ships both directions — consuming tools
> from configured MCP servers and exposing AutoPilot's own tools as an MCP
> server. 33 tests cover the protocol parsing, both transports, the adapter, and
> the server endpoint. Not implemented: SSE streaming transport, long-lived stdio
> sessions (a process is spawned per call batch), and resources/prompts
> primitives — only `initialize`, `tools/list`, and `tools/call`.

## As built

### Consuming external MCP tools

Configure the allow-list in `MCP_SERVERS` (JSON array):

```bash
MCP_SERVERS=[{"name":"files","transport":"stdio","command":"mcp-server-filesystem","args":["/data"]}]
MCP_SERVERS=[{"name":"remote","transport":"http","url":"https://host/mcp","headers":{"Authorization":"Bearer ..."}}]
```

At startup `discover_mcp_tools` connects to each server, calls `tools/list`, and
registers an `MCPToolAdapter` per remote tool into the **same** `tool_registry`
native tools use. Remote names are prefixed `mcp__` so they can never shadow a
native tool, and input models are synthesized from each tool's advertised JSON
Schema. Discovery is failure-isolated: an unreachable server logs and is skipped,
never blocking boot.

They then appear in `GET /api/v1/tools` with `origin: "mcp"` and are invocable
through `POST /api/v1/tools/{name}/invoke` like anything else.

### Serving AutoPilot as an MCP server

`POST /api/v1/tools/mcp` speaks JSON-RPC 2.0 (`initialize`, `tools/list`,
`tools/call`) over the native tools — `vector_search`, `web_search`,
`create_task`. MCP-origin tools are deliberately excluded so this endpoint never
becomes a proxy hop back to another server.

### Security

- `MCP_SERVERS` is the only source of servers; nothing discovers or trusts a
  server named by remote content.
- Tool results are **data, never instructions** — `parse_call_result` normalizes
  them into a dict and no caller executes them.
- `ToolMeta.permissions` on adapted tools is declarative only, matching native
  tools: this platform has no role model to enforce against (see
  `../COMPLETION_PLAN.md` §3).

## Original design sketch (retained)

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
