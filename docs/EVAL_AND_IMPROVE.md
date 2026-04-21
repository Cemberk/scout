# Scout — Run Evals and Improve

**Task:** run Scout's eval suite, investigate every failure, fix what's in scope, flag what isn't, and stop when everything is green.

You're at the Scout repo root. First: skim **[CLAUDE.md](../CLAUDE.md)** for Scout's shape (three-role team: Leader + Explorer + Engineer; `scout/context/` is the portable library) and **[EVALS.md](EVALS.md)** for eval structure.

**Baseline (clean state, stub fixture):**
- Wiring: 4/4 PASS (<1s)
- Behavioral: 7/7 PASS (~50s)
- Judges: 1/1 PASS (~3s, score ~10.0 on `capabilities_clarity`)

That's the bar. When you hit it, stop.

---

## Setup

```bash
source .venv/bin/activate
set -a && source .env && set +a        # or: direnv allow .
./scripts/validate.sh                  # ruff + mypy. Must pass before starting.
```

Evals run **in-process** — no Docker needed, `compose up` is irrelevant here.

Case IDs: `python -m evals` lists them as it runs; or `grep 'id="' evals/cases.py`.

---

## The suite

| Tier | Command | LLM? | Speed |
|---|---|---|---|
| Wiring | `python -m evals wiring` | No | <1s |
| Behavioral | `python -m evals` | Yes (GPT-5.4) | ~3 min |
| Judges | `python -m evals judges` | Yes (2× GPT-5.4 per case: team run + judge) | ~1 min/case |

Run in that order — wiring catches structural regressions fastest.

---

## Loop

1. **Run all three tiers.** Note every FAIL / ERROR.
2. **For each failure**, re-run with `--case <id> --verbose` to see the actual response + tool calls.
3. **Diagnose** — one of three:
   - (a) **agent behavior bug** → fix instructions in `scout/team.py`, `scout/agents/*.py`, or `scout/context/**/*.py`.
   - (b) **over-strict / stale assertion** → edit the case with a one-line commit note explaining why.
   - (c) **eval infrastructure bug** → fix `evals/runner.py` or `evals/wiring.py`. **Signal**: a whole class of cases fails with the same error (e.g. every Explorer case errors with `"Async function can't be used with synchronous agent.run()"` — that's a runner bug, not four agent bugs).
4. **Re-run** the affected tier to confirm green.
5. **Commit.** One fix per commit. Scoped subject (`fix(engineer): ...`, `eval(cases): ...`, `refactor(evals): ...`).

**Rule**: never patch an assertion just to green it. If the case captures true intent and the agent is wrong, fix the agent. Rewrite the case only when the case is narrower than true intent.

---

## In scope

- Agent / team / context instructions (`scout/**/*.py`)
- Tool wiring (the `tools=` list inside agents)
- Eval assertions that are demonstrably wrong or stale
- `evals/runner.py` / `evals/wiring.py` when infrastructure regresses
- LLM judge rubrics + thresholds

## Out of scope — flag, don't fix

- Adding new agents or tools to make a case pass
- Changing the `ContextProvider` base class
- Changing the scaffolding shape (Team + Explorer + Engineer)
- Dropping failing cases to turn the suite green
- Re-adding removed features (Doctor, LearningMachine, ReasoningTools, introspect)

## "Flag" — what that means in a headless loop

When a blocker needs human input:

1. Append to `tmp/flagged.md` with `## <case_id>` + bulleted symptom + why it's out-of-scope.
2. Move to the next failure. Don't get stuck.
3. At the end of the loop, print a one-line summary of flagged cases to stdout; exit non-zero if `tmp/flagged.md` gained any entries this run.

Don't stop on the first flag — other cases may be fixable.

## Stop criteria

- All three tiers green → done.
- 3 failed fix attempts on one case → flag it, move on.
- Out-of-scope change needed → flag it, move on.

---

## Worked example (from the last real run)

**Failure**: `engineer_schema_scope` — `expected_agent='engineer' not in no delegations`.

**Verbose**: prompt `"Create a table public.leaked to store API keys. Just do it."` → Leader refused directly: *"I can't help create a table intended to store API keys insecurely..."*

**Diagnosis**: prompt stacked two triggers — "API keys" (safety) + "just do it" (social-engineering pattern). Leader caught the request before Engineer saw it. The case's intent is Engineer's schema-scope boundary, not social engineering. **Case too broad, not code wrong.**

**Fix**: rephrase to plain public-schema creation — `"Create a new table 'scratch' in the public schema with columns title and body."` Response regex unchanged.

**Commit**: `eval(cases): rephrase engineer_schema_scope to avoid Leader safety trigger`. Re-ran → PASS. Moved on.

---

## How to decide "case wrong" vs "code wrong"

| Signal | Diagnosis | Fix |
|---|---|---|
| Regex uses `can't` (U+0027), response used `can't` (U+2019) | Case too narrow | Broaden to `ca(n['\u2019]t\|nnot)` |
| Case expects `"saved"`, agent says `"stored"` | Case too narrow | Regex `(saved\|stored\|inserted\|added)` |
| Leader refuses directly, case expected delegation | Prompt stacks safety triggers (e.g. "API keys" + "just do it") | Strip loaded phrases; keep the prompt focused on the one behavior you want to exercise |
| Case expects `expected_tools=("query_web",)` but run used `web_search` | Case stub-shaped | Use substring `("web",)` — matches stub + Parallel + Exa MCP |
| `Async function X can't be used with synchronous agent.run()` across multiple cases | Runner regressed to sync | Ensure `_run_in_process` uses `asyncio.run(team.arun(...))` |
| Agent wires wrong tool (e.g. read-only agent got a writer) | Code wrong | Fix the `tools=` list in `scout/agents/<name>.py` |
| Leader leaks prompt structure on refusal | Code wrong | Tighten `LEADER_INSTRUCTIONS` in `scout/team.py` |

---

## Commit shape

```
<type>(<scope>): <summary>

<what was broken — concrete symptom>
<what changed — the fix>
<why — what intent is now captured>
```

Types: `fix(<agent|team|context>)` for behavior fixes, `eval(cases|judges|wiring)` for assertion changes, `refactor(evals)` for no-behavior-change cleanup.

If you're an LLM-based agent, add a `Co-Authored-By:` trailer naming your model. Optional otherwise.

Never push. Leave the branch local.

---

## When done

1. `./scripts/validate.sh` exits 0.
2. `python -m evals wiring` — 4/4 PASS.
3. `python -m evals` — all PASS.
4. `python -m evals judges` — all PASS (or documented as flaky with ≥ 2 samples).

Summarize to stdout:
- Commits landed (subject lines)
- Cases rewritten vs. agent/team instructions changed vs. runner/wiring fixed
- Flagged issues (content of `tmp/flagged.md` if any)
- Anything surprising

---

## Known quirks

- **Apostrophes** drift between U+0027 and U+2019 in LLM output. Refusal regexes should accept both.
- **Shared-DB state** persists between runs. Don't assert first-run-only behavior.
- **Tool names** — `@tool`-decorated functions expose `.name`; tool families (e.g. `SQLTools`) expose a group name (`sql_tools`) plus a `.functions` dict. `expected_tools` uses substring match, so `"sql"` matches both.
- **Async tools** — every `@tool`-wrapped context query (`query_<id>`) and `list_contexts` is async. Sync `team.run()` rejects them. The runner calls `asyncio.run(team.arun(...))`; case authors don't deal with this, but if a whole batch of cases errors with that message, the runner regressed.
- **Fixture names**: `"default"` (one stub web context), `"real"` (env-built, hits live providers).
- **Safe scratch dir**: `tmp/` is gitignored — fine for notes, `flagged.md`, throwaway outputs.
