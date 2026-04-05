"""
security.py - input sanitization, output safety, and production runtime guards.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Tuple

MAX_INPUT_LENGTH = 10_000

# ---------------------------------------------------------------------------
# Unicode obfuscation defenses
# ---------------------------------------------------------------------------

# Zero-width, invisible, and bidirectional-override characters commonly used
# to hide injection payloads from human reviewers while keeping them machine-
# readable.  Strip these before pattern matching.
_ZERO_WIDTH_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad]"
)

# Cyrillic/Greek/Latin-extended homoglyphs → ASCII equivalents.
# Maps only visually-identical characters that appear in known injection attempts.
_HOMOGLYPH_MAP = str.maketrans({
    "\u0430": "a",  # Cyrillic а
    "\u0435": "e",  # Cyrillic е
    "\u043e": "o",  # Cyrillic о
    "\u0440": "r",  # Cyrillic р
    "\u0441": "c",  # Cyrillic с
    "\u0445": "x",  # Cyrillic х
    "\u0456": "i",  # Cyrillic і
    "\u03b5": "e",  # Greek ε
    "\u03bf": "o",  # Greek ο
    "\u0391": "A",  # Greek Α
    "\u0399": "I",  # Greek Ι
    "\u039f": "O",  # Greek Ο
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark
    "\u201c": '"',  # Left double quotation mark
    "\u201d": '"',  # Right double quotation mark
})


def _normalize_for_detection(text: str) -> str:
    """Strip zero-width chars, map homoglyphs to ASCII, then NFKC-normalize.
    Run before pattern matching to defeat Unicode-obfuscated injection payloads."""
    text = _ZERO_WIDTH_RE.sub("", text)
    text = text.translate(_HOMOGLYPH_MAP)
    return unicodedata.normalize("NFKC", text)


_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+(all\s+)?previous\s+instructions",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"print\s+(your\s+)?system\s+prompt",
        r"output\s+(your\s+)?system\s+prompt",
        r"(execute|run)\s+code",
        r"rm\s+-rf",
        r"delete\s+system",
        r"shutdown\s+(the\s+)?system",
        r"(drop|truncate)\s+table",
        r"<script[\s>]",
        r";\s*-{2}",
        r"UNION\s+SELECT",
        r"\/\*.*?\*\/",
        r"base64_decode",
        r"eval\s*\(",
        r"__import__\s*\(",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"you\s+are\s+now\s+(?:a|an|my)\s+\w",
        r"act\s+as\s+(?:if\s+)?(?:you\s+(?:are|were)\s+)?(?:a|an)\s+\w+\s+without\s+(any\s+)?restrictions",
        r"new\s+(?:system\s+)?instructions?\s*:",
        r"system\s*:\s*you\s+(are|must|should)",
        r"---+\s*(system|instructions?)\s*---+",
    ]
]

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

_INSECURE_SECRET_MARKERS = {"dev_secret_change_me", "change_me", "fallback", "dev", "development", "insecure", "test-secret"}


def assert_production_runtime_safety() -> None:
    environment = (os.getenv("ENVIRONMENT", "development") or "development").strip().lower()
    secret = (os.getenv("JWT_SECRET", "") or "").strip()
    lowered = secret.lower()
    if environment == "production":
        insecure = (not secret) or any(marker in lowered for marker in _INSECURE_SECRET_MARKERS)
        if insecure or len(secret) < 32:
            raise RuntimeError("Refusing to start in production: JWT_SECRET is missing, too short, or using a dev/fallback value.")


def sanitize_input(user_input: str) -> Tuple[str | None, str | None]:
    if not user_input:
        return "", None
    text = unicodedata.normalize("NFKC", user_input).strip()
    if len(text) > MAX_INPUT_LENGTH:
        return None, "Message too long. Please keep requests under 10,000 characters."
    # Run patterns against both the original and the homoglyph-normalized form
    # so Unicode-obfuscated injections are caught even when they evade NFKC alone.
    detection_text = _normalize_for_detection(text)
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text) or pattern.search(detection_text):
            return None, "Your message contains content that cannot be processed."
    return text, None


def safe_output(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    for phrase in _LEAK_PHRASES:
        if phrase in lowered:
            return "I'm here to help with your request."
    return text
