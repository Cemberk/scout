"""
Compiler Agent
==============

Iterates `[s for s in sources if s.compile]` and produces Obsidian-compatible
markdown under `context/compiled/articles/`.

Phase 1 wiring: the Compiler is mostly a thin shell around the runner in
scout/compile/runner.py. The runner is also called directly by:
- the every-10-min `wiki-compile` cron (POST /compile/run)
- the CLI: `python -m scout compile ...`

The Compiler agent itself remains useful for ad-hoc instructions like
"recompile only the entry I just edited" or for the Leader to delegate to.
"""

from agno.agent import Agent
from agno.models.openai import OpenAIResponses

from scout.agents.settings import agent_db, scout_knowledge
from scout.instructions import build_compiler_instructions
from scout.tools import build_compiler_tools

COMPILER_INSTRUCTIONS = """\
You are the Compiler. You convert raw sources into a curated, navigable
Obsidian-compatible wiki under context/compiled/articles/. The Navigator
reads the wiki — never the raw sources directly. You are the boundary.

## Your job

1. Call `read_manifest` to see which compile-on sources are reachable
   right now. (You can only see compile-on sources by design.)
2. Call `list_compile_sources` for the same view in JSON.
3. For routine work, call `compile_all_sources` (or `compile_one_source`
   for a single source). The runner:
   - Lists entries in the source.
   - Diffs against `scout_compiled` by source_hash.
   - Skips unchanged. Skips user-edited (writes a sibling instead).
   - For new/changed entries, generates Obsidian-compat markdown using
     `context/voice/wiki-article.md`.
   - Records every result in `scout_compiled` and inserts a `Wiki:` row
     in scout_knowledge.
4. For one-shot debugging — "compile this one entry" — use `compile_one`.
5. Use `list_compile_records` to see what's already been compiled.

## What you do NOT do

- Do not interact with users directly.
- Do not query Drive, Slack, email, or the web.
- Do not edit articles in `context/compiled/articles/` by hand. The
  runner is the only thing that writes there.
- Do not delete anything.
- Do not touch articles flagged `user_edited: true`. The runner already
  refuses to — don't try to override.

## When called from the cron

The default behaviour ("compile any new sources") is one call to
`compile_all_sources(force=False)`. Report a one-line summary
(`{source: counts by status}`) and stop.\
"""

compiler = Agent(
    id="compiler",
    name="Compiler",
    role="Iterates compile-on sources and produces Obsidian-compatible markdown wiki articles",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=build_compiler_instructions(COMPILER_INSTRUCTIONS),
    knowledge=scout_knowledge,
    search_knowledge=True,
    tools=build_compiler_tools(scout_knowledge),
    add_datetime_to_context=True,
    markdown=True,
)
