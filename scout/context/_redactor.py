"""
Redactor — strips secret-shaped strings from tool output.

``redact(text)`` runs text through a small set of regex patterns before
it reaches the model. Patterns are deliberately conservative — false
positives (masking something that looks like a token but isn't) are
preferred to leaks.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # OpenAI-style sk-... keys
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-…REDACTED"),
    # Generic Bearer tokens
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]{16,}"), "Bearer …REDACTED"),
    # GitHub PATs (classic + fine-grained)
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "ghp_…REDACTED"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_…REDACTED"),
    # Slack tokens
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "xox…REDACTED"),
    # Google API keys
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), "AIza…REDACTED"),
    # AWS keys
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA…REDACTED"),
    # Long base64-y blobs that look like JWTs
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "eyJ…REDACTED.JWT"),
    # KEY=value where key looks secret-ish (PASSWORD, SECRET, TOKEN, KEY)
    (
        re.compile(r"\b([A-Z][A-Z0-9_]*?(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY))\s*=\s*[^\s\"']+"),
        r"\1=…REDACTED",
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out
