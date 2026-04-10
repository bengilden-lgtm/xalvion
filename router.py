"""
router.py — cost-aware model routing.

Routes cheap/simple queries to the smaller model and complex/high-stakes
queries to the stronger one.  Called by agent.py::choose_model().
"""
from __future__ import annotations

import re

_CHEAP_KEYWORDS = frozenset([
    "status",
    "where is my order",
    "tracking",
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "how are you",
])

_EXPENSIVE_KEYWORDS = frozenset([
    "refund",
    "charged twice",
    "double charge",
    "damaged",
    "broken",
    "fraud",
    "dispute",
    "legal",
    "escalate",
    "cancel",
])


def route_task(user_input: str) -> str:
    """
    Returns 'cheap' or 'expensive'.

    Expensive wins if any expensive keyword matches.
    Cheap wins if only cheap keywords match and nothing expensive.
    Defaults to 'expensive' when ambiguous — better safe than wrong.
    """
    text = (user_input or "").lower()

    if any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in _EXPENSIVE_KEYWORDS):
        return "expensive"

    if any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in _CHEAP_KEYWORDS):
        return "cheap"

    # Default: use the stronger model for anything unrecognised
    return "expensive"
