# Scout Evals

Three tiers, one registry:

| Tier | Entry point | What it catches | Needs LLM? | Needs Docker? |
|---|---|---|---|---|
| **Wiring** (code-level invariants) | `python -m evals wiring` | Agent tools drift off-shape (reader wires a writer, writer wires a sender, Leader gains tools) | No | No |
| **Behavioral** (cases) | `python -m evals` | Leader routes wrong / agents over-tool / responses miss expected substrings / forbidden tools fire | Yes | No (default); `--live` for SSE |
| **Judges** (LLM-scored quality) | `python -m evals judges` | Grounded-answer quality (currently empty pending more providers) | Yes | No |

`scripts/validate.sh` runs the wiring tier on every invocation. Judges and behavioral stay out of validate because they hit the model.

## 1. Wiring — no LLM, no network

File: [`evals/wiring.py`](../evals/wiring.py).

Each invariant is a function that returns `None` on PASS and raises `AssertionError` with a diagnostic on FAIL. Today's set:

- `W1` Explorer's bound tools are read-only; expected helpers (`list_contexts`, `update_learnings`) present.
- `W2` Engineer wires `introspect_schema` + `update_learnings`; no outbound send tools.
- `W3` Doctor wires `status` / `status_all` / `db_status` / `env_report` / `update_learnings`; no writers.
- `W4` Leader has no tools (pure router).
- `W5` Every registered `ContextProvider` has the expected shape (`id`/`name` + `query`/`status`/`get_tools`/`instructions`).

```bash
python -m evals wiring          # exits 0 on PASS, non-zero on FAIL
./scripts/validate.sh           # runs wiring as its final step
```

## 2. Behavioral — cases, two transports

Files: [`evals/cases.py`](../evals/cases.py), [`evals/runner.py`](../evals/runner.py).

One flat `CASES` tuple. Fields:

- `prompt` — sent to the team
- `expected_agent` — `None` means Leader answers directly; else the id must appear in the delegated member list
- `response_contains` / `response_forbids` / `response_matches` (regex) — deterministic assertions
- `expected_tools` / `forbidden_tools` — substring match against tool names across leader + every delegated specialist
- `requires` / `requires_not` — env gating (SKIP, not FAIL)
- `fixture` — `"default"` (one stub web context) or `"none"` (empty)
- `max_duration_s`, `target_file`

Two transports share the case inventory:

```bash
python -m evals                       # in-process team.run(), default
python -m evals --case <id>           # single case
python -m evals --live                # POST /teams/scout/runs + parse SSE
python -m evals --verbose             # response + tool previews
```

Live mode uses whatever `PARALLEL_API_KEY` the container has set. The in-process path installs the fixture via `scout.contexts.set_runtime(contexts)` and refreshes Explorer's tools around each case.

On FAIL, a per-case diagnostic is written to [`evals/results/<case_id>.md`](../evals/results/). `scripts/eval_loop.sh` feeds that file to `claude -p` without re-running the case.

## 3. Judges — LLM-scored quality

File: [`evals/judges.py`](../evals/judges.py).

Currently empty. New cases will land here as the provider set expands.

```bash
python -m evals judges                # all judged cases
python -m evals judges --case <id>    # one case
python -m evals judges --verbose
```

## Shell env — load `.env` or nothing works

Anything that hits OpenAI directly from the host needs `.env` loaded:

1. `direnv allow .` — best
2. `set -a; source .env; set +a; python -m evals` — one-shot
3. `set -a && source .env && set +a && python -m evals ...` — per-invocation

Docker picks up `.env` automatically via `docker compose`.

## Autonomous fix loop

```bash
./scripts/eval_loop.sh <case_id>
# env: MAX_ATTEMPTS=5  BASE_URL=http://localhost:8000
```

Each attempt runs the case, and on FAIL hands the diagnostic to `claude -p` with a restricted toolset. After the edit it commits an `eval_loop: <case> attempt <n>` checkpoint, restarts `scout-api`, and loops until PASS or `MAX_ATTEMPTS`.
