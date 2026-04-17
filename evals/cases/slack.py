"""
Slack Interface Cases — Phase 1
===============================

Per spec §10: @scout in thread produces threaded reply with citations.

These are evaluated by message shape, not by Slack delivery. The test
phrases simulate what the Slack interface would forward to the team
runner. The Slack delivery itself is covered by an end-to-end harness
that lands with demo prep.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "The response should be Slack-shaped: short, direct, with citations "
    "rendered as either compiled/articles/<file>.md paths or as URLs. "
    "Citations are required when the agent draws on the wiki or Drive. "
    "Long preambles like 'Sure, I will check ...' are a FAIL. "
    "If the agent says nothing was found, that's fine — but it should "
    "say so explicitly."
)

CASES: list[str] = [
    "<@scout> what's our PTO policy?",
    "<@scout> where's the deploy runbook?",
    "<@scout> who owns the customer-health pipeline?",
]
