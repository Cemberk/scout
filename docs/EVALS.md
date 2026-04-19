# Scout Evals

Scout ships with four complementary eval tiers. Each tier answers a different question, and `python -m evals improve` can drive any of them as a feedback signal into an autonomous fix loop.

| Tier | Entry point | What it catches | Needs Docker? |
|---|---|---|---|
| **Gating smoke** | `python -m scout _smoke_gating` | Tool-layer gating broke (Navigator can read `local:raw`) | No |
| **Smoke** (in-process) | `python -m evals smoke` | Leader routes wrong / agents over-tool / governance regressions | No |
| **Static** (agno judges) | `python -m evals` | LLM-judged quality: refusals, voice, accuracy, reliability | No |
| **Live** (Docker SSE) | `python -m evals.live run` | End-to-end regressions against the real service surface | Yes — `scout-api` on `:8000` |

Failures at any tier become input to `python -m evals improve`, which reads the editable surface, asks GPT-5.4 for minimal exact-match edits, applies them, verifies, and commits on success (rolls back on regression).

## 1. Gating smoke — code-level invariant

File: [scout/__main__.py:86](scout/__main__.py:86) (`_cmd_smoke_gating`)

Builds a real `Manifest`, then calls `source_read("local:raw", ...)` through Navigator-role tools. Contract: this **must** raise `PermissionError`. If anything else happens — content returned, other exception — gating is broken and nothing else in the build is safe.

```bash
python -m scout _smoke_gating          # exits 0 on PASS, non-zero on FAIL
./scripts/validate.sh                   # runs this inside the validation pipeline
```

No LLM, no network, no Docker. Fastest possible feedback that the `compile=True / live_read=False` invariant still holds.

## 2. Smoke — in-process, deterministic

File: [evals/smoke.py](evals/smoke.py)

Runs the Scout team directly (no SSE, no Docker). Every assertion is deterministic — substring / regex / tool-call patterns — so runs are fast and cheap. There is **no LLM judge** in this tier.

Groups ([`SmokeTest.group`](evals/smoke.py:40)): `warmup`, `routing`, `governance`, `wiki`, `knowledge`, `gating`.

Each case ([`SmokeTest`](evals/smoke.py:37)) declares:

- `prompt` — what gets sent to the team
- `response_contains` / `response_not_contains` / `response_matches` — substring + regex assertions (case-insensitive)
- `expected_tools` / `forbidden_tools` — substring-matched against tool names across the leader + every delegated member
- `requires` / `requires_not` — env gating
- `depends_on` — skip if prereq didn't PASS (used to chain a "save discovery" then "recall discovery" test)
- `max_duration_s`

```bash
python -m evals smoke                         # all groups
python -m evals smoke --group routing         # one group
python -m evals smoke --case routing.navigator_wiki
python -m evals smoke --verbose               # print response + tool previews
```

Exit code 0 if nothing FAILed or ERRORed; SKIP doesn't fail the run.

## 3. Static — agno judges

Files: [evals/run.py](evals/run.py), [evals/__init__.py](evals/__init__.py), [evals/cases/](evals/cases/)

Built on agno's `AccuracyEval`, `AgentAsJudgeEval`, and `ReliabilityEval`. Judge model is `OpenAIResponses(id="gpt-5.4")`. Each category is a module in `evals/cases/` with a `CASES` list (and `CRITERIA` for judge categories, plus optional `SKIP_IF_MISSING` for env gating).

Categories registered in [CATEGORIES](evals/__init__.py:17):

| Category | Type | What it checks |
|---|---|---|
| `security` | judge_binary | No secret values leak in output |
| `routing` | reliability | Leader fires the expected tool call |
| `governance` | judge_binary | Refusals for writes, deletes, out-of-scope asks |
| `knowledge` | accuracy | Factual match against expected output (1-10, threshold 7) |
| `voice` | judge_numeric | Draft matches the relevant voice guide (threshold 7) |
| `wiki` | reliability | Wiki questions route through `source_find` etc. |
| `wiki_compile` | judge_binary | Compiled-only reads; raw reads refused |
| `manifest` | judge_binary | Unconfigured source → explicit refusal, not silent fallback |
| `isolation` | judge_binary | Per-user SQL scoping |
| `drive_live` | judge_binary | Drive live-read behavior (env-gated) |
| `slack` | judge_binary | Slack live-read behavior (env-gated) |
| `code_explorer` | judge_binary | On-demand clone + read-only exploration |
| `s3_compile` | judge_binary | S3 source compile path (env-gated) |
| `engineer` | judge_binary | Writes land in a `scout_*` table + recorded to Knowledge |
| `doctor` | judge_binary | Grounded health report, no secret leaks, no user-data writes |

```bash
python -m evals                         # every category (env-gated ones SKIP if unset)
python -m evals --category engineer     # one category
python -m evals --verbose               # show response previews + failure reasons
```

Env-dependent categories `SKIP` rather than `FAIL` when their `SKIP_IF_MISSING` vars are unset.

### Shell env — don't ask, source it

Anything that hits OpenAI / Google directly from the host needs `.env` loaded. In order:

1. `direnv allow .` — best; every shell in this repo has the env
2. `set -a; source .env; set +a; python -m evals` — one-shot
3. `set -a && source .env && set +a && python -m evals ...` — per-invocation via Bash tool

Docker picks up `.env` automatically via `docker compose`, so only host invocations need this.

## 4. Live — Docker SSE harness

Files: [evals/live/cases.py](evals/live/cases.py), [evals/live/runner.py](evals/live/runner.py), [evals/live/client.py](evals/live/client.py), [evals/live/__main__.py](evals/live/__main__.py)

End-to-end: POST the prompt to `/teams/scout/runs`, parse the SSE stream agno emits, assemble a `RunResult`, assert against the case, and on FAIL write a markdown diagnostic to `evals/results/<case_id>.md`. Each case names a **single target file** that an auto-fix loop may edit.

Inventory (55 cases total, 51 local + 4 env-gated) — see [evals/live/cases.py:8](evals/live/cases.py:8):

- Meta / leader-direct (7)
- Gating — `local:raw` refusal (8)
- Prompt-injection resistance (5)
- Routing — Navigator (6)
- Routing — Compiler (6)
- Governance (local-only) (6)
- Wiki / Navigator behavior (5)
- Response format (3)
- Robustness (4)
- CodeExplorer (1 — keyless public repo)
- Env-gated (4 — SKIP without env)

Each [`EvalCase`](evals/live/cases.py:41) declares:

- `prompt`
- `expected_agent` — `None` means the Leader answers directly; otherwise the id must appear in `add_member_run`
- `response_contains` / `response_forbids` — case-insensitive
- `expected_tools` / `forbidden_tools` — exact match against `tool_name` from SSE events
- `max_duration_s`
- `target_file` — the one file Claude Code is allowed to edit when this case fails
- `requires` — env vars that must be set (SKIP otherwise)

```bash
# start the service first
docker compose up -d scout-api

python -m evals.live run                      # everything
python -m evals.live run --case greeting      # one case
python -m evals.live run --base-url http://localhost:8000
```

On FAIL, look in [evals/results/](evals/results/): per-case `*.md` diagnostics include the prompt, member responses, tool calls, the last 200 lines of `docker compose logs scout-api`, the current contents of `target_file`, and a terse instruction block telling Claude Code to edit only that file. A per-run `summary-*.json` is also written.

### Autonomous fix loop per case

```bash
./scripts/eval_loop.sh gating_adversarial
# env: MAX_ATTEMPTS=5  BASE_URL=http://localhost:8000
```

Each attempt runs the case, and on FAIL hands the diagnostic to `claude -p` with `--allowed-tools Read,Edit,Grep,Glob` (no Bash — the harness controls the loop). After the edit it commits an `eval_loop: <case> attempt <n>` checkpoint so every step is revertable, restarts `scout-api`, and loops until PASS or `MAX_ATTEMPTS`.

## 5. Improve loop — drive any tier

File: [evals/improve.py](evals/improve.py)

Reads failures, asks GPT-5.4 for minimal exact-match string edits against a whitelisted surface, applies them with Python syntax validation + per-file rollback, verifies the tier again, regressions-check against the before-map, and commits each non-regression round.

```bash
python -m evals improve                 # 3 rounds, smoke tier
python -m evals improve --tier live
python -m evals improve --tier static --rounds 2
python -m evals improve --dry-run --verbose    # analyze + print diff, don't edit
python -m evals improve --no-commit            # run but skip git commit per round
```

Whitelisted edit surface ([`ALLOWED_FILES`](evals/improve.py:39)):

- `scout/instructions.py`, `scout/team.py`, `scout/tools/build.py`
- `scout/agents/{navigator,compiler,code_explorer,engineer,doctor}.py`

Anything outside this set is rejected even if the analyzer proposes it. Per-round backups live next to the file as `*.bak.round-N` and are cleaned up at the end. Artifacts are written to `evals/results/improve-round-N.json`.

Invariants the analyzer is told never to break (see [ANALYZER_SYSTEM_PROMPT](evals/improve.py:92)):

1. `python -m scout _smoke_gating` must stay exit-0
2. Drafts-only Gmail/Calendar unless `SCOUT_ALLOW_SENDS=true`
3. Navigator/Doctor/Leader stay on the read-only SQL engine
4. No new deps, agents, sources, or tools
5. Wiki citations use compiled paths, never raw
6. SQL stays scoped to `user_id`

## When to run which tier

- **After any tool-binding change** — gating smoke first (`python -m scout _smoke_gating`), then smoke
- **Before opening a PR** — `./scripts/validate.sh` + `python -m evals smoke`
- **After touching routing / instructions** — `python -m evals smoke --group routing` + relevant static category
- **End-to-end sanity on a branch** — `docker compose up -d scout-api` + `python -m evals.live run`
- **One case keeps failing** — `./scripts/eval_loop.sh <case_id>`
- **Multiple failures, want a programmatic fix** — `python -m evals improve --tier smoke`

## Adding cases

- Smoke — append a [`SmokeTest`](evals/smoke.py:37) to `CASES` in `evals/smoke.py`. Keep it tight: every case must earn its slot.
- Static — add to (or create) a module in `evals/cases/` with a `CASES` list (and `CRITERIA` for judge types, `SKIP_IF_MISSING` if env-gated). Register it in [CATEGORIES](evals/__init__.py:17).
- Live — append an [`EvalCase`](evals/live/cases.py:41) to `CASES` in `evals/live/cases.py`. Set `target_file` to the single file you'd edit to fix it — that's what the auto-fix loop will modify.
