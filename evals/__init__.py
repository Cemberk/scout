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
    "wiki_compile": {"type": "judge_binary", "module": "evals.cases.wiki_compile"},
    "manifest": {"type": "judge_binary", "module": "evals.cases.manifest"},
    "isolation": {"type": "judge_binary", "module": "evals.cases.isolation"},
    "drive_live": {"type": "judge_binary", "module": "evals.cases.drive_live"},
    "slack": {"type": "judge_binary", "module": "evals.cases.slack"},
    "code_explorer": {"type": "judge_binary", "module": "evals.cases.code_explorer"},
    "s3_compile": {"type": "judge_binary", "module": "evals.cases.s3_compile"},
    "engineer": {"type": "judge_binary", "module": "evals.cases.engineer"},
    "doctor": {"type": "judge_binary", "module": "evals.cases.doctor"},
}
