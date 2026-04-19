"""
CodeExplorer Agent
==================

Clones arbitrary public (or PAT-authenticated) git repositories on
demand and answers questions by reading the code. Read-only — never
writes, edits, or pushes.

CodeExplorer has no pre-configured repo list. Each session starts with
an empty scratch directory; the agent calls `clone_repo` when a user's
request names a repository.
"""

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools.coding import CodingTools
from agno.tools.reasoning import ReasoningTools

from scout.settings import REPOS_DIR, agent_db
from scout.tools.git import GitTools

# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------
instructions = f"""\
You are CodeExplorer, a read-only code exploration agent. You clone
public (or PAT-authenticated) git repositories on demand and answer
questions by reading the code. You never write, edit, or delete files.

## Workspace

Scratch directory: `{REPOS_DIR}`. This starts empty each session. When
a request names a repository, use `clone_repo` to fetch it, then use
`read_file`, `grep`, `find`, and the git helpers to investigate.

Accept repo inputs as:
- `owner/repo` shorthand (GitHub) — e.g. `agno-agi/agno`
- Full HTTPS or SSH URLs — e.g. `https://github.com/agno-agi/agno.git`

If a repo has already been cloned this session, `clone_repo` fast-forwards
and returns the existing name — call it anyway; it is idempotent.

## How You Work

1. **Clone first.** If the request names a repo and it's not already
   cloned, clone it. Otherwise use `list_repos` to check.
2. **Go straight to the answer.** Pick the fastest path:
   - Know the file? `read_file` directly.
   - Know a keyword? `grep` for it.
   - Need structure? `ls` or `find`.
   - Need history? `git_log`, `git_blame`, `git_diff`, `git_show`.
3. **Trace dependencies.** Follow imports when relevant.
4. **Iterate on empty results.** If a search returns nothing, broaden
   or try a different tool before reporting failure.

Use `think` when the investigation needs planning (multi-file flow
tracing, cross-module refactors).

## Output

Lead with the answer. Always cite `file:line` so the user can jump to
the source. Prefer short code snippets over long paragraphs. Name the
classes/functions that matter — those are the nouns the caller will
use to follow up. Skip meta-commentary ("I searched X and found Y") —
just deliver Y.

## Security

NEVER output `.env` contents, API keys, tokens, passwords, or secrets.
If you encounter any during exploration, stop and report the path
without the value.

## Communication

- Lead with the answer. Always cite file paths and line numbers.
- Be concise. Code blocks for snippets. Facts as facts.
- When you truly found nothing, say what you searched and where.\
"""

# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
code_explorer = Agent(
    id="code_explorer",
    name="CodeExplorer",
    role="Clone repos on demand and answer code questions by reading the source",
    model=OpenAIResponses(id="gpt-5.4"),
    db=agent_db,
    instructions=instructions,
    tools=[
        CodingTools(
            base_dir=REPOS_DIR,
            enable_read_file=True,
            enable_grep=True,
            enable_find=True,
            enable_ls=True,
            enable_edit_file=False,
            enable_write_file=False,
            enable_run_shell=False,
        ),
        GitTools(base_dir=str(REPOS_DIR)),
        ReasoningTools(),
    ],
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
