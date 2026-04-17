"""
Scout Evaluations
==================

Eval framework for testing Scout's capabilities.

Usage:
    python -m evals
    python -m evals --category routing
    python -m evals --verbose
"""

from agno.models.openai import OpenAIResponses

JUDGE_MODEL = OpenAIResponses(id="gpt-5.4")

CATEGORIES: dict[str, dict] = {
    "security": {"type": "judge_binary", "module": "evals.cases.security"},
    "routing": {"type": "reliability", "module": "evals.cases.routing"},
    "governance": {"type": "judge_binary", "module": "evals.cases.governance"},
    "knowledge": {"type": "accuracy", "module": "evals.cases.knowledge"},
    "voice": {"type": "judge_numeric", "module": "evals.cases.voice"},
    "wiki": {"type": "reliability", "module": "evals.cases.wiki"},
    "documents": {"type": "accuracy", "module": "evals.cases.documents"},
    # v3 Phase 1 additions
    "wiki_compile": {"type": "judge_binary", "module": "evals.cases.wiki_compile"},
    "manifest": {"type": "judge_binary", "module": "evals.cases.manifest"},
    "isolation": {"type": "judge_binary", "module": "evals.cases.isolation"},
    "drive_live": {"type": "judge_binary", "module": "evals.cases.drive_live"},
    "slack": {"type": "judge_binary", "module": "evals.cases.slack"},
    "github_live": {"type": "judge_binary", "module": "evals.cases.github_live"},
    "s3_compile": {"type": "judge_binary", "module": "evals.cases.s3_compile"},
}
