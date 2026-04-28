# Git-Backed Knowledge Wiki

Scout ships with the knowledge wiki on the local filesystem
(`wiki/knowledge/`). Pages live on whatever host runs Scout. Fine for a
demo. Not fine for a real deployment — restart the container and the
wiki is gone, share the host across environments and pages diverge.

`GitBackend` swaps the storage layer for a real git repository. Every
`update_knowledge` call stages the changed files, commits with an
LLM-summarised one-line message, rebases onto the remote, and pushes.
You get durability, an audit trail, and a place reviewers can leave
comments on what Scout has learned.

The voice wiki stays filesystem-backed. Voice rules are code-managed by
design — change them via PR to the scout repo, not via the agent.

## Setup

### 1. Create the wiki repo

A new private repo on GitHub. One file is enough to start:

```sh
gh repo create your-org/your-wiki --private --add-readme
```

Default branch `main` works. Branch can be configured later.

### 2. Mint a fine-grained PAT

GitHub → Settings → Developer settings → Personal access tokens →
**Fine-grained tokens** → **Generate new token**.

- **Resource owner**: your org (or your user)
- **Repository access**: only `your-org/your-wiki`
- **Repository permissions** → **Contents**: **Read and write**

Copy the `github_pat_*` value.

> The PAT is registered with `agno.context.wiki.GitBackend`'s `Scrubber`
> on construction — it will not appear in any log line, including stderr
> from a failed git invocation.

### 3. Set env vars

In `.env`:

```sh
WIKI_REPO_URL=https://github.com/your-org/your-wiki.git
WIKI_GITHUB_TOKEN=github_pat_***
# Optional:
WIKI_BRANCH=main                       # defaults to main
WIKI_LOCAL_PATH=/var/lib/scout/wiki    # where the clone lives on disk
```

### 4. Switch the factory

In [`scout/contexts.py`](../scout/contexts.py), replace
`_create_knowledge_wiki()`:

```python
from os import getenv

from agno.context.wiki import GitBackend, WikiContextProvider


def _create_knowledge_wiki() -> WikiContextProvider:
    return WikiContextProvider(
        id="knowledge",
        name="Company Knowledge",
        backend=GitBackend(
            repo_url=getenv("WIKI_REPO_URL", ""),
            branch=getenv("WIKI_BRANCH", "main"),
            github_token=getenv("WIKI_GITHUB_TOKEN", ""),
            local_path=getenv("WIKI_LOCAL_PATH"),  # None -> default tmp clone
        ),
        model=default_model(),
    )
```

That's the entire code change. The provider keeps the same id (`knowledge`)
and the same tools (`query_knowledge`, `update_knowledge`) — Scout's
prompts and evals don't need to know which backend is wired in.

### 5. Restart Scout

The first `update_knowledge` call clones the repo into `WIKI_LOCAL_PATH`
(or a default tmp path if unset), writes the page, commits with an
LLM-summarised message, rebases onto the remote, and pushes.

Subsequent calls reuse the clone.

## What gets committed

One commit per `update_knowledge` call. Commit messages are
LLM-summarised from the diff, no trailers, single line. The author is
`Agno Wiki Bot <wiki-bot@agno.local>` by default — override via the
`author_name` / `author_email` kwargs on `GitBackend`.

The git history is the audit trail. `git log -p wiki/knowledge/` shows
exactly what Scout has filed and when.

## Conflicts

If the remote has moved since the last write, the backend rebases
locally before pushing. If rebase fails (genuine content conflict on
the same lines), the call returns an error — Scout surfaces it to the
caller rather than silently overwriting.
