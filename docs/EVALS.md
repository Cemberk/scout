# Scout Evals

Scout comes with three tiers of evaluations:

| Tier | Entry point | What it catches | Needs LLM? |
|---|---|---|---|
| **Wiring** (code-level invariants) | `python -m evals wiring` | Scout's tool shape drifts (bare SQL leaks onto Scout, CRM provider loses `update_crm`, schema guard disappears) | No |
| **Behavioral** (cases) | `python -m evals` | Scout picks the wrong tool / responses miss expected substrings / forbidden tools fire | Yes |
| **Judges** (LLM-scored quality) | `python -m evals judges` | Answer quality, anything a regex can't express | Yes |

`scripts/validate.sh` runs `ruff` + `mypy` only. Wiring / behavioral / judges are direct `python -m evals ...` invocations; the LLM-hitting tiers aren't wired into pre-commit.

> **PostgreSQL must be running for every tier, including wiring.** The CRM provider builds `SQLTools(db_engine=get_sql_engine(), …)` / `get_readonly_engine()` at module import, and both engines open a connection + bootstrap the `scout` schema on first call. Start the DB container (`docker compose up -d scout-db`) before running any eval tier.

## 1. Wiring — no LLM, no network

File: [`evals/wiring.py`](../evals/wiring.py).

Each invariant is a function that returns `None` on PASS and raises `AssertionError` with a diagnostic on FAIL.

- `W1` Scout has `query_crm` + `update_crm` + `list_contexts`; no bare `SQLTools` on Scout (SQL belongs inside the CRM provider).
- `W2` `DatabaseContextProvider` exposes both `query_crm` and `update_crm`; `aupdate` is overridden.
- `W3` The scout engine's `before_cursor_execute` hook rejects DDL/DML against `public` / `ai`.
- `W4` Every registered `ContextProvider` has the expected shape (`id`/`name` + `query`/`status`/`get_tools`/`instructions`).
- `W5` `GDriveContextProvider` uses `AllDrivesGoogleDriveTools` (the shared-drive-aware subclass).
- `W6` `MCPContextProvider` implements the lifecycle interface cleanly — exposes `query_mcp_<slug>`, `aclose` is safe pre-connect, `status()` doesn't raise when unconnected, sync `query()` refuses (MCP is async-only).
- `W7` Scout sets a sentinel default `user_id` so callers that don't identify themselves can't leak the `{user_id}` prompt template into CRM SQL.

```bash
python -m evals wiring          # exits 0 on PASS, non-zero on FAIL
```

## 2. Behavioral — cases, in-process

Files: [`evals/cases.py`](../evals/cases.py), [`evals/runner.py`](../evals/runner.py).

One flat `CASES` tuple. Fields:

- `prompt` — sent to Scout
- `expected_agent` — kept for back-compat; with single-agent Scout, leave as `None` (runner skips the delegation check)
- `response_contains` / `response_forbids` / `response_matches` (regex) — deterministic assertions
- `expected_tools` / `forbidden_tools` — substring match against tool names Scout called this turn
- `fixture` — `"default"` (stub web/slack/gdrive + real CRM) or `"real"` (env-built contexts; hits actual providers)
- `max_duration_s`
- `followups` — additional turns in the same session (for memory / multi-turn flows)

Example (from [`evals/cases.py`](../evals/cases.py)):

```python
Case(
    id="scout_greeting",
    prompt="hey",
    response_contains=("scout",),
    forbidden_tools=("query_", "update_"),
    max_duration_s=45,
)
```

```bash
python -m evals                       # in-process agent.arun()
python -m evals --case <id>           # single case
python -m evals --verbose             # response + tool previews
```

On FAIL, the failure reasons are printed inline. Re-run with `--case <id> --verbose` to drill in.

## 3. Judges — LLM-scored quality

File: [`evals/judges.py`](../evals/judges.py).

Fields on the `Judged` dataclass:

- `prompt` — sent to the team
- `criteria` — the rubric handed to `AgentAsJudgeEval`. Each bullet is a point budget the judge allocates.
- `scoring` — `"numeric"` (0–10, pass at `passing_score`) or `"binary"` (pass/fail).
- `passing_score` — numeric threshold (default `7.0`).
- `fixture` — same shapes as behavioral.
- `max_duration_s` — budget for the team run; the judge itself is separate.

```bash
python -m evals judges                # all judged cases
python -m evals judges --case <id>    # one case
python -m evals judges --verbose      # responses + judge reason on FAIL
```

## Shell env

The LLM tiers hit OpenAI/Parallel from the host, so `.env` must be loaded. See [CLAUDE.md — Environment loading](../CLAUDE.md#environment-loading-for-cli-work). Docker picks up `.env` automatically via `docker compose`.

## Fixing a failing case

Paste [`docs/EVAL_AND_IMPROVE.md`](EVAL_AND_IMPROVE.md) into a fresh Claude Code session. It runs the suite, diagnoses each failure, fixes what's in scope (assertions, prompts, params), and flags what isn't.

Blockers that need human judgment get appended to `tmp/flagged.md` (gitignored) as `## <case_id>` + symptom + why it's out-of-scope. That's the handoff surface — read it when you come back.
