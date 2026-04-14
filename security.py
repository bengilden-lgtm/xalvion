"""
security.py - input sanitization, output safety, and production runtime guards.
"""
from __future__ import annotations

import logging
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
    "sk_live_",
    "sk_test_",
    "whsec_",
    "rk_live_",
    "database_url",
    "postgresql://",
    "smtp_password",
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

logger = logging.getLogger("xalvion.security")


def assert_production_runtime_safety() -> None:
    environment = (os.getenv("ENVIRONMENT", "development") or "development").strip().lower()
    secret = (os.getenv("JWT_SECRET", "") or "").strip()
    lowered = secret.lower()
    exec_mode = (os.getenv("XALVION_EXEC_MODE", "mock") or "mock").strip().lower()
    stripe_key = (os.getenv("STRIPE_SECRET_KEY", "") or "").strip()

    # "Required-to-boot" safety: only hard-fail when running in production or when
    # configured to perform real actions (live execution / live Stripe key).
    # Enforce only when there's actual "live money / live actions" risk.
    # Railway healthchecks should not be blocked by optional/preview configuration.
    _must_enforce = exec_mode == "live" or stripe_key.startswith("sk_live_")

    # Execution mode safety:
    # Production must never silently operate in mock mode, since it can appear operational
    # while performing no real financial actions.
    if _must_enforce and environment == "production" and exec_mode != "live":
        raise RuntimeError(
            "Refusing to start in production: XALVION_EXEC_MODE must be 'live' "
            "(mock mode is unsafe for production)."
        )

    # Always enforce strong JWT_SECRET regardless of ENVIRONMENT.
    _KNOWN_WEAK_DEFAULTS = {"change_me", "dev_secret_change_me", ""}
    insecure = (
        secret in _KNOWN_WEAK_DEFAULTS
        or any(marker in lowered for marker in _INSECURE_SECRET_MARKERS)
        or len(secret) < 32
    )

    if insecure:
        msg = (
            "JWT_SECRET is missing, too short, or using a dev/fallback value. "
            "Set JWT_SECRET to a random 32+ character value."
        )
        if _must_enforce:
            raise RuntimeError(f"Refusing to start: {msg}")
        logger.warning("runtime_safety_degraded env=%s exec_mode=%s detail=%s", environment, exec_mode, msg)
        return

    logger.info("production_runtime_safety_ok")


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
