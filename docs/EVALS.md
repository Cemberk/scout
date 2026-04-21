# Scout Evals

Scout comes with three tiers of evaluations:

| Tier | Entry point | What it catches | Needs LLM? |
|---|---|---|---|
| **Wiring** (code-level invariants) | `python -m evals wiring` | Agent tools drift off-shape (reader wires a writer, Leader gains tools) | No |
| **Behavioral** (cases) | `python -m evals` | Leader routes wrong / agents over-tool / responses miss expected substrings / forbidden tools fire | Yes |
| **Judges** (LLM-scored quality) | `python -m evals judges` | Answer quality, routing clarity, anything a regex can't express | Yes |

`scripts/validate.sh` runs `ruff` + `mypy` only. Wiring / behavioral / judges are direct `python -m evals ...` invocations; the LLM-hitting tiers aren't wired into pre-commit.

> **PostgreSQL must be running for every tier, including wiring.** The Engineer agent builds `SQLTools(db_engine=get_sql_engine(), …)` at module import, and `get_sql_engine()` opens a connection + bootstraps the `scout` schema on first call. Start the DB container (`docker compose up -d scout-db`) before running any eval tier.

## 1. Wiring — no LLM, no network

File: [`evals/wiring.py`](../evals/wiring.py).

Each invariant is a function that returns `None` on PASS and raises `AssertionError` with a diagnostic on FAIL.

- `W1` Explorer's bound tools are read-only; `list_contexts` present.
- `W2` Engineer wires SQL writes; no outbound send tools.
- `W3` Leader has no tools (pure router).
- `W4` Every registered `ContextProvider` has the expected shape (`id`/`name` + `query`/`status`/`get_tools`/`instructions`).

```bash
python -m evals wiring          # exits 0 on PASS, non-zero on FAIL
```

## 2. Behavioral — cases, in-process

Files: [`evals/cases.py`](../evals/cases.py), [`evals/runner.py`](../evals/runner.py).

One flat `CASES` tuple. Fields:

- `prompt` — sent to the team
- `expected_agent` — `None` means Leader answers directly; else the id must appear in the delegated member list
- `response_contains` / `response_forbids` / `response_matches` (regex) — deterministic assertions
- `expected_tools` / `forbidden_tools` — substring match against tool names across leader + every delegated specialist
- `fixture` — `"default"` (one stub web context) or `"real"` (env-built contexts; hits actual providers)
- `max_duration_s`

Example (from [`evals/cases.py`](../evals/cases.py)):

```python
Case(
    id="leader_greeting",
    prompt="hey",
    expected_agent=None,
    response_contains=("scout",),
    forbidden_tools=("query_",),
    max_duration_s=45,
)
```

```bash
python -m evals                       # in-process team.run()
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

The LLM tiers hit OpenAI/Parallel/Exa from the host, so `.env` must be loaded. See [CLAUDE.md — Environment loading](../CLAUDE.md#environment-loading-for-cli-work). Docker picks up `.env` automatically via `docker compose`.

## Fixing a failing case

Paste [`docs/EVAL_AND_IMPROVE.md`](EVAL_AND_IMPROVE.md) into a fresh Claude Code session. It runs the suite, diagnoses each failure, fixes what's in scope (assertions, prompts, params), and flags what isn't.

Blockers that need human judgment get appended to `tmp/flagged.md` (gitignored) as `## <case_id>` + symptom + why it's out-of-scope. That's the handoff surface — read it when you come back.
