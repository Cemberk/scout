"""
CodeExplorer Cases
==================

CodeExplorer clones a public repo on demand and answers a question
about its code. No env gating — public repos clone tokenless, the
`repos` volume is scratch.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "The response must cite a concrete file path (and ideally a line "
    "number) inside the cloned repo. If a repo was named in the prompt "
    "and the Leader did not route to CodeExplorer, that fails. The "
    "response must not fabricate code — if CodeExplorer truly can't "
    "find what was asked, it should say what it searched and where."
)

CASES: list[str] = [
    "In the agno-agi/agno repo, find where Team.coordinate is defined. Cite the file and line.",
    "What does the agno-agi/agno README say this repo is for? Quote one short sentence.",
]
