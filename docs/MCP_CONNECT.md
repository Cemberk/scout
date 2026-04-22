# Connecting Scout to MCP Servers

Scout can pull any [Model Context Protocol](https://modelcontextprotocol.io) server into its context registry. Each configured server becomes one `MCPContextProvider`, exposes a single `query_mcp_<slug>` tool on Scout, and runs behind a dedicated sub-agent so tool-name collisions between MCP servers stay isolated.

## Why run an MCP server as a context

- **No custom provider to write** — point at any stdio/HTTP MCP server and Scout can use it immediately.
- **Tool discovery stays fresh.** The sub-agent's instructions are built from the server's `list_tools()` response at connect time, so rename a tool on the server and Scout picks it up on next restart.
- **Graceful degradation.** A crashed or unreachable server surfaces as `ok=false` on `/contexts/<id>/status` instead of taking Scout down.

## Configure

Each server is configured via env vars. List the slugs you want registered in `MCP_SERVERS`, then fill in the per-slug variables using the `MCP_<SLUG>_*` prefix.

```bash
MCP_SERVERS=linear,github,filesystem

# --- linear: local stdio server launched via npx ------------------------------
MCP_LINEAR_TRANSPORT=stdio
MCP_LINEAR_COMMAND=npx
MCP_LINEAR_ARGS=-y,@linear/mcp
MCP_LINEAR_ENV=LINEAR_API_KEY=${LINEAR_API_KEY}

# --- github: hosted streamable-http server ------------------------------------
MCP_GITHUB_TRANSPORT=streamable-http
MCP_GITHUB_URL=https://mcp.github.com/mcp
MCP_GITHUB_HEADERS=Authorization=Bearer ${GITHUB_TOKEN}

# --- filesystem: local stdio server over a fixed directory --------------------
MCP_FILESYSTEM_TRANSPORT=stdio
MCP_FILESYSTEM_COMMAND=npx
MCP_FILESYSTEM_ARGS=-y,@modelcontextprotocol/server-filesystem,/tmp/mcp-test
```

### Config schema

| Variable | When | Description |
|---|---|---|
| `MCP_SERVERS` | Always | Comma-separated slugs. Each slug registers as `mcp_<slug>`. |
| `MCP_<SLUG>_TRANSPORT` | Always | One of `stdio`, `sse`, `streamable-http`. |
| `MCP_<SLUG>_COMMAND` | stdio | Executable name (`npx`, `uvx`, `python`, etc.). |
| `MCP_<SLUG>_ARGS` | stdio (optional) | Comma-separated CLI args. |
| `MCP_<SLUG>_ENV` | stdio (optional) | `key=value` pairs, comma-separated. Supports `${VAR}` interpolation. |
| `MCP_<SLUG>_URL` | sse / streamable-http | Server URL. |
| `MCP_<SLUG>_HEADERS` | sse / streamable-http (optional) | `key=value` pairs, comma-separated. Supports `${VAR}` interpolation. |
| `MCP_<SLUG>_TIMEOUT_SECONDS` | All (optional) | Override the 30-second default MCP read timeout. |

### `${VAR}` interpolation

`MCP_*_HEADERS` and `MCP_*_ENV` values are interpolated against the process environment at load time. If a referenced variable is missing, the provider is skipped with a warning rather than passing an empty auth header — that 401 would otherwise be hard to diagnose downstream.

## Lifecycle

- **Connect is lazy.** The first `query_mcp_<slug>(...)` call pays the `MCPTools.initialize()` cost. `/contexts/<id>/status` also triggers a connect.
- **Sub-agent instructions come from `list_tools()`** — if the server updates its tool set, restart Scout to pick up the changes.
- **Shutdown closes sessions cleanly.** The app lifespan awaits `aclose()` across every registered provider with `return_exceptions=True` so one stuck teardown can't block the others.

## Verifying

```bash
curl -sS http://localhost:8000/contexts | jq '.[] | select(.id | startswith("mcp_"))'
# { "id": "mcp_linear", "name": "linear", "ok": true,  "detail": "mcp: linear (12 tools)" }
# { "id": "mcp_github", "name": "github", "ok": false, "detail": "mcp github: TimeoutError: ..." }
```

Then ask Scout a question that should route via the MCP tool:

```bash
curl -sS -X POST http://localhost:8000/agents/scout/runs \
  -H "Content-Type: application/json" \
  -d '{"message":"Search Linear for issues assigned to me this week","user_id":"demo"}' \
  | jq -r '.content'
```

## Debugging

- **`MCP server '<slug>' misconfigured: ...` on startup.** Env-var problem — the warning names the specific variable. Fix the env and restart.
- **`/contexts/mcp_<slug>/status` returns `ok=false`.** Either the server isn't reachable or `initialize()` errored. For stdio: check that `COMMAND` is on `PATH` (inside the container if running under compose). For HTTP: curl the URL directly to confirm it's live and your headers auth.
- **Tool calls fail but status is OK.** Look at `MCPContextProvider` logs — agno's `MCPTools` logs tool-call exceptions at `ERROR`. Some servers declare tools they don't actually implement; `exclude_tools` support isn't wired yet (flagged as future work).
- **Tool list looks stale.** The list is cached at connect time. Restart Scout to re-discover.

## Known gaps (v1)

- **Writes aren't gated.** If an MCP server exposes a `create_issue` tool, Scout's sub-agent will call it when the user explicitly asks. There's no per-tool policy layer yet.
- **No auto-reconnect.** A dropped session raises on the next call; the provider resets and the call after that reconnects. No retry loop beyond that.
- **No YAML config.** Env-driven only. Revisit if >5 servers with complex headers become the norm.
- **`list_contexts` shows tool counts, not tool schemas.** If you need the schema for a specific server, call the sub-agent directly or inspect `MCPTools.functions` in a debug shell.
