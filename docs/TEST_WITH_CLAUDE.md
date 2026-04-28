# Scout — Smoke-test the Live Container

**Task:** smoke-test a running Scout container by issuing curl requests and verifying the response + tool calls in the docker logs. Use this when you want a black-box sanity check of a deployment without typing prompts into the AgentOS UI.

For deterministic in-process tests, use [EVAL_AND_IMPROVE.md](EVAL_AND_IMPROVE.md) — this doc is for live-container probes against real APIs.

## Setup

Confirm the container is up and reachable:

```bash
docker ps --format '{{.Names}}\t{{.Status}}'   # scout-api should be Up
curl -sS http://localhost:8000/health          # {"status":"ok",...}
curl -sS http://localhost:8000/contexts | jq   # list registered providers
```

The `/contexts` response tells you which providers lit up. Note which are `ok=true` and skip the conditional tests for ones that aren't (Slack/GDrive/MCP only register when their env triggers are set).

If `localhost:8000` isn't right (different port, remote deploy), adjust the URL. If the container isn't named `scout-api`, adjust the `docker logs` calls.

For a one-time inventory of every tool registered on Scout:

```bash
docker logs scout-api 2>&1 | grep "Added tool" | sort -u
```

## Pattern — three commands per test

```bash
# 1. Send the prompt (multipart/form-data; AgentOS rejects JSON for /runs)
curl -sS -X POST http://localhost:8000/agents/scout/runs \
  -F 'message=YOUR PROMPT' \
  -F 'user_id=claude-test-42' \
  -F 'stream=false' \
  -o /tmp/scout-out.json -w "HTTP %{http_code} in %{time_total}s\n"

# 2. Read the response
jq -r '.content // .' < /tmp/scout-out.json

# 3. See which tools fired in the most recent run (filter by recency)
docker logs scout-api --since 30s 2>&1 | grep -E "Tool Calls|Name: '|Running:" | head -40
```

`--since <Ns>` (or `--since <ISO timestamp>`) keeps you to the just-issued run.

The `Tool Calls` lines include both Scout's outer tools (`query_web`, `query_slack`, …) and any inner sub-agent tools (`web_search`, `list_channels`, …). Assertions should match on the outer tool name — that's the routing decision that matters.

For multi-turn cases, capture the first response's `session_id` (`jq -r '.session_id' < /tmp/scout-out.json`) and pass `-F 'session_id=<value>'` on the next call. Or skip session reuse — `user_id` alone scopes most CRM round-trips.

## Test cases

Send each prompt with `user_id=claude-test-42` so the CRM sub-agent's `{user_id}` template substitutes consistently across turns.

| # | Prompt | Expected tools | Forbidden tools | Response should contain |
|---|---|---|---|---|
| 1 | `hi` | none | `query_`, `update_` | `scout` |
| 2 | `Which contexts are registered?` | `list_contexts` | — | `crm`, `web` |
| 3 | `Search the web for one fact about the Python language and cite the source.` | `query_web` | `update_` | `http` (a URL) |
| 4a | `Save a note titled 'docker-smoke' with body 'live container check'.` | `update_crm` | `update_knowledge` | `saved` / `stored` / `noted` |
| 4b | `List my notes titled 'docker-smoke'.` | `query_crm` | — | `docker-smoke` |
| 5 | `File a knowledge page titled 'docker-smoke' with body 'live container verified via Claude Code'.` | `update_knowledge` | `update_crm` | `saved` / `filed` / `wrote` |
| 6 | `Draft a one-line Slack message announcing wiki support. Consult the voice rules first.` | `query_voice` | `update_voice` | (a draft message — short, no preamble) |
| 7 | `Search the web for the Q4 2099 release notes for the purple-unicorn project.` | `query_web` | — | `no results` / `couldn't find` / `not found` (NOT a fabricated answer) |

**Conditional cases** — run only if the provider is in `/contexts` with `ok=true`:

| # | Prompt | Expected tools | Note |
|---|---|---|---|
| 8 | `Search Slack for messages about the Q4 roadmap.` | `query_slack` | If response says `missing_scope`, that's an OAuth scope problem on the installed Slack app — flag separately, don't fail the case. |
| 9 | `Search Google Drive for any file about 'roadmap'.` | `query_gdrive` | If response says no files found, that's expected when no folders are shared with Scout's service account — flag separately. |

## Report format

End with a one-screen summary. Don't dump full responses or full log greps.

```
TEST RESULTS — <date>

[PASS] 1. Greeting
[PASS] 2. Live context registry
[FAIL] 3. Web query — query_web fired but response had no URL
       response head: "I couldn't find Python information..."
       tools fired: query_web
[PASS] 4. CRM round-trip
...

Skipped: 8 (Slack not in /contexts), 9 (GDrive ok=false)

Notes:
- <anything surprising worth flagging>
```

For each FAIL: include the first 2-3 lines of the response and the relevant log lines. Nothing more.

## When done

- All non-conditional cases (1-7) PASS, OR
- Failures are reported with what broke. Best-guess diagnosis (agent prompt drift, model behavior changed, provider misconfigured) is welcome but not required.

**Don't fix anything in this loop — testing only.** If a real bug surfaces, hand it back with the failure detail; the fix loop is [EVAL_AND_IMPROVE.md](EVAL_AND_IMPROVE.md).
