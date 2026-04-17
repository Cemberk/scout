"""
GitHub Live-Read Cases — Phase 1
================================

Per spec §13: two cases — a ripgrep hit in a cloned repo cites
`owner/repo:path:line`, and an ad-hoc public repo URL triggers
`search/code`.

Skipped when GITHUB_REPOS / GITHUB_READ_TOKEN aren't set — we cannot
exercise a live GitHub token in the default eval run.

Eval type: AgentAsJudgeEval (binary)
"""

SKIP_IF_MISSING: tuple[str, ...] = ("GITHUB_REPOS", "GITHUB_READ_TOKEN")

CRITERIA = (
    "If GitHub is reachable in the manifest, the response should cite a "
    "GitHub blob URL (https://github.com/<owner>/<repo>/blob/...) with a "
    "line hint for any content drawn from a cloned repo, OR a "
    "search/code hit for ad-hoc public-repo lookups. If GitHub is not "
    "reachable, the response must say so explicitly rather than "
    "fabricating code. Silent fabrication fails."
)

CASES: list[str] = [
    "Find the JWT middleware in our acme/api repo and cite the file path and line.",
    "Search github.com/openai/openai-python for where `ChatCompletion` is defined.",
]
