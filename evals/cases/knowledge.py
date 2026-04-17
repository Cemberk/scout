"""
Knowledge Cases
===============

Agent correctly navigates context systems: reads files, queries SQL,
searches knowledge, and understands its own architecture.
Eval type: AccuracyEval (1-10 score)
"""

CASES: list[dict] = [
    {
        "input": "Read the about-us file",
        "expected_output": "Should return the contents of context/about-us.md including company background, team structure, stack, and current focus.",
        "guidelines": "Must include actual content from the file, not a summary of what it might contain.",
    },
    {
        "input": "What templates do we have available?",
        "expected_output": "Should list meeting-notes.md, weekly-review.md, and project-brief.md from context/templates/.",
        "guidelines": "Must list all three templates by name.",
    },
    {
        "input": "What can you do?",
        "expected_output": "Should describe Scout's capabilities: saving notes, reading files, enterprise document navigation, email/calendar (if configured), web research, wiki compilation, and the knowledge base pipeline.",
        "guidelines": "Must mention at least 4 distinct capabilities. Should not claim capabilities it doesn't have.",
    },
    {
        "input": "How do you handle email?",
        "expected_output": "Should explain that email is via Gmail, send is disabled, always creates drafts, and requires Google OAuth credentials.",
        "guidelines": "Must mention drafts and that sending is disabled. If Gmail is not configured, should give the fallback message.",
    },
    {
        "input": "What knowledge systems do you use?",
        "expected_output": "Should describe scout_knowledge (metadata routing) and scout_learnings (operational memory), plus the wiki and SQL as additional systems.",
        "guidelines": "Must mention at least knowledge and learnings as distinct systems.",
    },
    {
        "input": "What scheduled tasks do you run?",
        "expected_output": "Should list the 8 scheduled tasks: context refresh, daily briefing, wiki compile, inbox digest, learning summary, weekly review, wiki lint, and sync pull.",
        "guidelines": "Must mention at least 5 of the 8 tasks with approximate schedules.",
    },
]
