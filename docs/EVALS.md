# Scout Evals

Three tiers, one registry:

| Tier | Entry point | What it catches | Needs LLM? | Needs Docker? |
|---|---|---|---|---|
| **Wiring** (code-level invariants) | `python -m evals wiring` | Agent tools drift off-shape (reader wires a writer, writer wires a sender, Leader gating breaks, backend path-escape regresses) | No | No |
| **Behavioral** (cases) | `python -m evals` | Leader routes wrong / agents over-tool / responses miss expected substrings / forbidden tools fire | Yes | No (default); `--live` for SSE |
| **Judges** (LLM-scored quality) | `python -m evals judges` | Voice drift in drafts; grounded-answer quality | Yes | No |

`scripts/validate.sh` runs the wiring tier on every invocation. Judges and behavioral stay out of validate because they hit the model.

## 1. Wiring — no LLM, no network

File: [`evals/wiring.py`](../evals/wiring.py).

Each invariant is a function that returns `None` on PASS and raises `AssertionError` with a diagnostic on FAIL. The runner collects exceptions and reports. Today's set (`W1`–`W7`):

- `W1` Explorer's bound tools are read-only (no `ingest_*` / `send_*`).
- `W2` Engineer wires `ingest_url` / `ingest_text` / `trigger_compile` / `introspect_schema` / `update_learnings`; no send tools.
- `W3` Doctor wires `health` / `health_all` / `db_health` / `env_report` / `update_learnings`; no writers.
- `W4` Leader's send tools align with `SCOUT_ALLOW_SENDS` + Slack/Google env.
- `W5` Every registered `ContextProvider` has the expected shape (`id`/`name`/`kind` + `health`/`query`).
- `W6` `WikiContextProvider` has the five-method shape (`health` / `query` / `ingest_url` / `ingest_text` / `compile`).
- `W7` `LocalWikiBackend` rejects `../` path escapes on `read_bytes` + `write_bytes`.

```bash
python -m evals wiring          # exits 0 on PASS, non-zero on FAIL
./scripts/validate.sh           # runs wiring as its final step
```

## 2. Behavioral — cases, two transports

Files: [`evals/cases.py`](../evals/cases.py), [`evals/runner.py`](../evals/runner.py).

One flat `CASES` tuple. Each case names the section of [`tmp/spec.md`](../tmp/spec.md) it verifies; if you can't name the section, the case doesn't belong. Fields:

- `prompt` — sent to the team
- `expected_agent` — `None` means Leader answers directly; else the id must appear in the delegated member list
- `response_contains` / `response_forbids` / `response_matches` (regex) — deterministic assertions
- `expected_tools` / `forbidden_tools` — substring match against tool names across leader + every delegated specialist
- `requires` / `requires_not` — env gating (SKIP, not FAIL)
- `fixture` — `"default"` (stub wiki + stubs for one local + one slack), `"none"` (empty), `"writable_wiki"` (real `LocalWikiBackend` in a tmpdir)
- `max_duration_s`, `target_file`

Two transports share the case inventory:

```bash
python -m evals                       # in-process team.run(), default
python -m evals --case <id>           # single case
python -m evals --live                # POST /teams/scout/runs + parse SSE
python -m evals --verbose             # response + tool previews
```

Live mode uses whatever `SCOUT_WIKI` / `SCOUT_CONTEXTS` the container has running. The in-process path installs the fixture via `scout.tools.ask_context.set_runtime(wiki, contexts)` and then refreshes Explorer + Engineer tools around each case so the per-provider `query_<id>` tools match the fixture.

On FAIL, a per-case diagnostic is written to [`evals/results/<case_id>.md`](../evals/results/). `scripts/eval_loop.sh` feeds that file to `claude -p` without re-running the case — each attempt edits the case's `target_file`, restarts the service, and loops until PASS or `MAX_ATTEMPTS`.

## 3. Judges — LLM-scored quality

File: [`evals/judges.py`](../evals/judges.py).

Small tier — cap at ten across voice + grounded-answer. If a case can be expressed deterministically, it belongs in `cases.py`; if it genuinely needs a judge, it lives here. Judge is `OpenAIResponses(id="gpt-5.4")`. Voice cases score numerically (≥7 passes); answer-quality cases are binary (judge sets `.passed`).

```bash
python -m evals judges                # all judged cases
python -m evals judges --case <id>    # one case
python -m evals judges --verbose
```

## Shell env — load `.env` or nothing works

Anything that hits OpenAI directly from the host needs `.env` loaded:

1. `direnv allow .` — best; every shell in this repo has the env
2. `set -a; source .env; set +a; python -m evals` — one-shot
3. `set -a && source .env && set +a && python -m evals ...` — per-invocation

Docker picks up `.env` automatically via `docker compose`, so only host invocations need this.

## Autonomous fix loop

```bash
./scripts/eval_loop.sh <case_id>
# env: MAX_ATTEMPTS=5  BASE_URL=http://localhost:8000
```

Each attempt runs the case, and on FAIL hands the diagnostic to `claude -p` with a restricted toolset. After the edit it commits an `eval_loop: <case> attempt <n>` checkpoint so every step is revertable, restarts `scout-api`, and loops until PASS or `MAX_ATTEMPTS`.
