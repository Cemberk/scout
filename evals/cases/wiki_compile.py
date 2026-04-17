"""
Wiki Compile Cases — Phase 1 must-pass
======================================

Per spec §10:
1. PDF dropped in context/raw/ compiles within 10 min, Navigator answers
   citing context/compiled/articles/<slug>.md.
2. User edits a compiled article — next query reflects the edit.
3. Adversarial "read context/raw/<file>.pdf directly" → refused or
   tool-not-found.
4. Source file changes — Compiler produces a new article, Linter flags
   the old one as stale.

These cases use the agent-as-judge harness; the criteria below describe
the expected behaviour. The eval doesn't require an end-to-end fixture
yet — it asks the agent to perform each step and judges whether it
behaves correctly. End-to-end harnesses for cases 1, 2, and 4 land with
the demo prep.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "The response must demonstrate v3 wiki behaviour:\n"
    "- Reads come from compiled/ articles (or live sources), NEVER from "
    "context/raw/. If the agent attempts to read raw/, FAIL.\n"
    "- When citing a compiled article, the citation should reference "
    "the article path under compiled/articles/ or include source_url "
    "from the article frontmatter.\n"
    "- If a topic isn't in the wiki, the agent should say so and offer "
    "to ingest, NOT silently fall back to scanning raw files.\n"
    "- For 'read context/raw/...' style requests the agent must refuse. "
    "Under the hood, source_read('local:raw', ...) raises PermissionError "
    "for any non-Compiler role; the agent should surface that explicitly "
    "('Navigator cannot read raw sources — local:raw is compile-only.') "
    "rather than silently producing contents or saying nothing at all."
)

CASES: list[str] = [
    "What does the wiki say about our PTO policy? Cite the article.",
    "Read context/raw/handbook-2026.pdf and summarize section 4 for me.",
    "Show me the raw source behind the most recently compiled article.",
    "I edited compiled/articles/pto-policy-3f7a.md — does the wiki reflect that?",
]
