"""Scout evals — one case registry, two transports, small judged tier.

Structure:
- ``cases.py``     — behavioral cases (Case dataclass + CASES tuple)
- ``runner.py``    — in-process + SSE transport, fixtures, diagnostics
- ``wiring.py``    — code-level invariants (no LLM, no team.run())
- ``judges.py``    — LLM-scored quality tier (voice + grounded-answer)
- ``__main__.py``  — CLI dispatch

Entry points:
    python -m evals                          # behavioral, in-process
    python -m evals --live                   # behavioral via SSE
    python -m evals --case <id>              # single case
    python -m evals wiring                   # code-level invariants
    python -m evals judges                   # LLM-scored tier
    ./scripts/eval_loop.sh <case_id>         # Claude-driven fix loop
"""

from evals.cases import CASES, CASES_BY_ID, Case, get
from evals.runner import RESULTS_DIR, CaseResult, run_case, write_diagnostic

__all__ = [
    "CASES",
    "CASES_BY_ID",
    "Case",
    "CaseResult",
    "RESULTS_DIR",
    "get",
    "run_case",
    "write_diagnostic",
]
