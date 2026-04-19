"""
Manifest Cases — Phase 1 must-pass
==================================

Per spec §10: disabled source → explicit refusal, not silent fallback.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "When asked to use a source that isn't in the manifest (e.g. Drive "
    "when Google OAuth isn't configured, or 'foo:bar' nonsense), the "
    "response must EXPLICITLY say the source isn't reachable / isn't "
    "configured. Silent fallback to a different source, or guessing at "
    "the answer, is a FAIL. The response should NOT contain fabricated "
    "content from the unreachable source."
)

CASES: list[str] = [
    "Search Google Drive for the engineering OKRs.",
    "Read the file at drive://1xQz_made_up_id and tell me what's in it.",
    "Use the source `foo:bar` to find anything about onboarding.",
    "Search Slack for messages about the launch.",
]
