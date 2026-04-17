"""Scout live-eval harness.

Runs prompts against the Docker-hosted team over SSE, asserts structured
expectations, and emits per-case diagnostics for Claude Code to consume
when a case fails.

Modelled on ../vibe-video/evals — same contract, Scout-shaped cases.

    python -m evals.live run                       # all cases
    python -m evals.live run --case gating         # one case
    python -m evals.live run --base-url http://localhost:8000

    scripts/eval_loop.sh gating                    # autonomous fix loop
"""
