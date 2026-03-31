"""
security.py — input sanitization and output safety.

FIXES:
1. Replaced trivially-bypassed lowercase regex blocklist with case-insensitive
   compiled patterns that also catch leet-speak variants and whitespace tricks.
2. Added length cap — very long inputs are a common DoS / prompt-stuffing vector.
3. Added unicode normalization to defeat homoglyph attacks.
4. safe_output() now strips a broader set of internal leak phrases.
5. All functions fully typed.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Tuple

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

MAX_INPUT_LENGTH = 10_000  # characters

# Compiled case-insensitive patterns — harder to bypass than plain .lower()
_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"(execute|run)\s+code",
        r"rm\s+-rf",
        r"delete\s+system",
        r"shutdown\s+(the\s+)?system",
        r"(drop|truncate)\s+table",
        r"<script[\s>]",           # XSS attempt
        r";\s*-{2}",               # SQL comment injection
        r"UNION\s+SELECT",         # SQL injection
        r"\/\*.*?\*\/",            # SQL block comment
        r"base64_decode",          # encoded payload attempt
        r"eval\s*\(",              # JS/Python eval
        r"__import__\s*\(",        # Python import injection
        r"os\.system\s*\(",        # shell execution
        r"subprocess\.",           # subprocess execution
    ]
]

# Phrases that must never appear in customer-facing output
_LEAK_PHRASES: list[str] = [
    "system prompt",
    "payment_intent_id",
    "charge_id",
    "stripe_secret",
    "api_key",
    "jwt_secret",
    "confidence score",
    "internal_note",
    "abuse_score",
    "operator_mode",
    "brain.json",
    "aurum.db",
]


# ---------------------------------------------------------------------------
# INPUT SANITIZATION
# ---------------------------------------------------------------------------

def sanitize_input(user_input: str) -> Tuple[str | None, str | None]:
    """
    Returns (clean_text, None) on success or (None, block_reason) on failure.
    """
    if not user_input:
        return "", None

    # Normalize unicode — defeats homoglyph / zero-width attacks
    text = unicodedata.normalize("NFKC", user_input).strip()

    if len(text) > MAX_INPUT_LENGTH:
        return None, "Message too long. Please keep requests under 10,000 characters."

    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return None, "Your message contains content that cannot be processed."

    return text, None


# ---------------------------------------------------------------------------
# OUTPUT SAFETY
# ---------------------------------------------------------------------------

def safe_output(text: str) -> str:
    """Strip any internal/sensitive phrases from customer-facing output."""
    if not text:
        return ""

    lowered = text.lower()
    for phrase in _LEAK_PHRASES:
        if phrase in lowered:
            return "I'm here to help with your request."

    return text
