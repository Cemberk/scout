# MCP Context Providers

`MCPContextProvider` wraps a single [Model Context Protocol](https://modelcontextprotocol.io) server as a Scout context. Any MCP server becomes a registered context without writing new code — this is Scout's escape hatch for sources that don't have a first-class provider yet.

## Configuring

Point `SCOUT_MCP_CONFIG` at a YAML file. Each top-level list entry becomes one provider:

```yaml
# mcp_servers.yaml
- id: notion
  name: Notion
  command: "npx -y @modelcontextprotocol/server-notion"
  env:
    NOTION_API_KEY: "secret_***"

- id: sequential-thinking
  name: Sequential Thinking
  command: "npx -y @modelcontextprotocol/server-sequential-thinking"

- id: exa-hosted
  name: Exa (hosted MCP)
  url: "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
  transport: "streamable-http"
```

## Fields

| Field | Required | Purpose |
|---|---|---|
| `id` | Yes | Stable identifier. Becomes `query_<id>` on the calling agent. |
| `name` | No | Human-readable name (defaults to `id`). |
| `command` | One of `command`/`url` | Full command + args, space-separated (stdio transport). |
| `url` | One of `command`/`url` | Endpoint for HTTP MCP servers. |
| `transport` | No | `stdio`, `sse`, or `streamable-http`. Defaults to `stdio` when `command` is set, `streamable-http` when `url` is set. |
| `env` | No | Environment variables passed to the stdio subprocess. |

## How it's registered

`scout/contexts.py::build_contexts()` reads `SCOUT_MCP_CONFIG` at startup. Each entry is instantiated as an `MCPContextProvider` and appended to the context list. Explorer picks up the MCP tools on its next run (contexts are resolved fresh every run).

If the YAML fails to parse or an entry raises during construction, the entry is skipped with a warning — the rest of the registry still builds.

## Checking it's wired

```sh
python -m scout contexts          # lists every registered context + status
curl http://localhost:8000/contexts
```

Both show each MCP provider's `id` and `name` with `ok: true` once the config loads.
