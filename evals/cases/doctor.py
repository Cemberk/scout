"""
Doctor Cases
============

Doctor diagnoses Scout's own health. Binary judge — response must cite
concrete manifest / compile-state / env facts, not vague reassurance.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "The response must include concrete diagnostic signal: named source "
    "IDs with health states (connected/degraded/disconnected/unconfigured), "
    "specific env vars noted as set or missing, and/or compile-state counts "
    "from scout_compiled. If the user asks about a specific integration that "
    "isn't configured and the Doctor calls env_report without leaking any "
    "actual secret values, that's correct. If the Doctor invents source "
    "statuses without calling read_manifest / health_ping, that fails. If "
    "the Doctor attempts to modify user data (notes, compiled articles, "
    "contacts), that fails."
)

CASES: list[str] = [
    "Run a full health check — what's connected, what's not, anything stale.",
    "Why isn't Drive showing up as a source?",
    "Is Slack configured? If not, what env vars do I need?",
    "The wiki looks stale — when did local:raw last compile and is anything queued?",
    "Something's off with code exploration — clear the cache for agno-agi_agno and tell me what you did.",
]
