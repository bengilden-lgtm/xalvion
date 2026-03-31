"""
feedback.py — quality-driven rule reinforcement.

FIX: The original called add_rule() on a local brain copy without saving.
     add_rule() already calls save_brain() internally, so the fix is to
     load a fresh brain, mutate it via add_rule(), and let add_rule handle
     the save.  No orphaned writes.
"""
from __future__ import annotations

from brain import add_rule, load_brain, save_brain


def process_feedback(user_input: str, response: str, quality: float) -> None:
    brain = load_brain()

    if quality < 0.5:
        add_rule(brain, {
            "trigger": "low_quality_response",
            "condition": {},
            "action": {"type": "none", "amount": 0},
        })

    if quality > 0.8:
        add_rule(brain, {
            "trigger": "clarity_confidence_rule",
            "condition": {},
            "action": {"type": "none", "amount": 0},
        })

    # add_rule calls save_brain internally — explicit save kept as safety net
    save_brain(brain)
