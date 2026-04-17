"""
Voice Cases
===========

Agent drafts content that matches the voice guide for the target platform.
Eval type: AgentAsJudgeEval (numeric, threshold 7)
"""

CRITERIA = (
    "Evaluate how well the agent's response matches the expected voice and format:\n"
    "1. Reads the correct voice guide before drafting.\n"
    "2. Tone matches the guide — direct, no fluff, no banned words.\n"
    "3. Structure follows the guide — hooks, bullets, length constraints.\n"
    "4. No banned openings or phrases from the guide's anti-patterns.\n"
    "5. Content is grounded in real context, not generic filler.\n\n"
    "A score of 7+ means the draft is ready to use with minor tweaks. "
    "Below 5 means it violates the voice guide or reads like generic AI output."
)

CASES: list[str] = [
    "Draft a Slack message to the team about the API migration status",
    "Draft an email to the engineering leads about the upcoming architecture review",
    "Write a one-page technical document comparing two deployment strategies, with a clear recommendation",
    "Draft a Slack message announcing the new PTO policy changes",
]
