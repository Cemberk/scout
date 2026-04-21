# Scout Evals

Three tiers, one registry:

| Tier | Entry point | What it catches | Needs LLM? | Needs Docker? |
|---|---|---|---|---|
| **Wiring** (code-level invariants) | `python -m evals wiring` | Agent tools drift off-shape (reader wires a writer, writer wires a sender, Leader gains tools) | No | No |
| **Behavioral** (cases) | `python -m evals` | Leader routes wrong / agents over-tool / responses miss expected substrings / forbidden tools fire | Yes | No (default); `--live` for SSE |
| **Judges** (LLM-scored quality) | `python -m evals judges` | Grounded-answer quality, citation discipline, capabilities clarity | Yes | Only for `fixture="real"` cases that need live web |

`scripts/validate.sh` runs `ruff` + `mypy` only. Wiring / behavioral / judges are all direct `python -m evals ...` invocations; the LLM-hitting tiers aren't wired into pre-commit.

## 1. Wiring — no LLM, no network

File: [`evals/wiring.py`](../evals/wiring.py).

Each invariant is a function that returns `None` on PASS and raises `AssertionError` with a diagnostic on FAIL. Today's set:

- `W1` Explorer's bound tools are read-only; `list_contexts` present.
- `W2` Engineer wires SQL writes; no outbound send tools.
- `W3` Leader has no tools (pure router).
- `W4` Every registered `ContextProvider` has the expected shape (`id`/`name` + `query`/`status`/`get_tools`/`instructions`).

```bash
python -m evals wiring          # exits 0 on PASS, non-zero on FAIL
```

## 2. Behavioral — cases, two transports

Files: [`evals/cases.py`](../evals/cases.py), [`evals/runner.py`](../evals/runner.py).

One flat `CASES` tuple. Fields:

- `prompt` — sent to the team
- `expected_agent` — `None` means Leader answers directly; else the id must appear in the delegated member list
- `response_contains` / `response_forbids` / `response_matches` (regex) — deterministic assertions
- `expected_tools` / `forbidden_tools` — substring match against tool names across leader + every delegated specialist
- `fixture` — `"default"` (one stub web context), `"none"` (empty), or `"real"` (env-built contexts; hits actual providers)
- `max_duration_s`, `target_file`

Two transports share the case inventory:

```bash
python -m evals                       # in-process team.run(), default
python -m evals --case <id>           # single case
python -m evals --live                # POST /teams/scout/runs + parse SSE
python -m evals --verbose             # response + tool previews
```

Live mode uses whatever `PARALLEL_API_KEY` the container has set. The in-process path installs the fixture via `scout.contexts.publish_contexts(contexts)`; Explorer reads the fresh registry on its next run via its callable `tools=` factory.

On FAIL, the failure reasons are printed inline. Pipe through `less` or re-run with `--case <id> --verbose` to drill in.

## 3. Judges — LLM-scored quality

File: [`evals/judges.py`](../evals/judges.py).

Fields on the `Judged` dataclass:

- `prompt` — sent to the team
- `criteria` — the rubric handed to `AgentAsJudgeEval`. Each bullet is a point budget the judge allocates.
- `scoring` — `"numeric"` (0–10, pass at `passing_score`) or `"binary"` (pass/fail).
- `passing_score` — numeric threshold (default `7.0`).
- `fixture` — same shapes as behavioral. Defaults to `"real"` so the judge grades real backend output, not stub canned text.
- `max_duration_s` — budget for the team run; the judge itself is separate.

Seeded cases:

| Case | What it grades |
|---|---|
| `grounded_url_summary` | Does the answer about Agno draw concrete features from `docs.agno.com` and cite a URL under that domain? |
| `capabilities_clarity` | Does "what can you do?" name both specialists concretely and avoid over-promising? (uses `fixture="default"`) |
| `citation_discipline` | When asked to cite a source, does the answer include a real URL that corresponds to a specific claim? |

```bash
python -m evals judges                # all judged cases
python -m evals judges --case <id>    # one case
python -m evals judges --verbose      # responses + judge reason on FAIL
```

Judges that use `fixture="real"` hit live providers — they require the same env (`OPENAI_API_KEY`, optionally `PARALLEL_API_KEY` / `EXA_API_KEY`) as running the app.

## Shell env — load `.env` or nothing works

Anything that hits OpenAI directly from the host needs `.env` loaded:

1. `direnv allow .` — best
2. `set -a; source .env; set +a; python -m evals` — one-shot
3. `set -a && source .env && set +a && python -m evals ...` — per-invocation

Docker picks up `.env` automatically via `docker compose`.

## Fixing a failing case

Paste [`tmp/eval_and_improve.md`](../tmp/eval_and_improve.md) into a fresh Claude Code session. It runs the suite, reads failures, fixes what's in scope (assertions, prompts, params), and flags what isn't.
