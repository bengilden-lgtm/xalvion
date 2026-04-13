"""
feedback.py — post-response quality hook.

Scalar quality scores are not mapped into brain rules: empty-condition rules
matched every ticket and degraded routing. Rule learning stays in learning.py
(outcome- and ticket-driven) with validated conditions.
"""
from __future__ import annotations


def process_feedback(user_input: str, response: str, quality: float) -> None:
    """Reserved for analytics or future supervised signals; does not mutate rules."""
    _ = (user_input, response, quality)
