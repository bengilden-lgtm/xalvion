"""
security.py - input sanitization, output safety, and production runtime guards.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Tuple

MAX_INPUT_LENGTH = 10_000

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
        r"<script[\s>]",
        r";\s*-{2}",
        r"UNION\s+SELECT",
        r"\/\*.*?\*\/",
        r"base64_decode",
        r"eval\s*\(",
        r"__import__\s*\(",
        r"os\.system\s*\(",
        r"subprocess\.",
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
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
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
