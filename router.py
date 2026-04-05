"""
router.py — cost-aware model routing.

Routes cheap/simple queries to the smaller model and complex/high-stakes
queries to the stronger one.  Called by agent.py::choose_model().

Scoring replaces binary first-match: each keyword carries a weight,
accumulated scores are compared against a threshold.  Expensive wins ties
and unknowns — better safe than wrong.
"""
from __future__ import annotations

# keyword → routing weight (higher = stronger signal)
_CHEAP_KEYWORDS: dict[str, float] = {
    "status":           1.0,
    "where is my order": 1.2,
    "tracking":         1.0,
    "hello":            1.5,
    "hi":               1.5,
    "hey":              1.5,
    "thanks":           1.5,
    "thank you":        1.5,
    "how are you":      1.5,
    "order update":     1.0,
    "when will":        0.8,
}

_EXPENSIVE_KEYWORDS: dict[str, float] = {
    "refund":           2.0,
    "charged twice":    2.5,
    "double charge":    2.5,
    "duplicate charge": 2.5,
    "damaged":          2.0,
    "broken":           2.0,
    "fraud":            3.0,
    "dispute":          2.5,
    "legal":            3.0,
    "escalate":         2.0,
    "cancel":           1.5,
    "not received":     1.5,
    "missing":          1.5,
    "wrong item":       2.0,
    "lost":             1.5,
    "chargeback":       3.0,
    "unauthorized":     2.5,
    "never arrived":    2.0,
    "still waiting":    1.2,
    "weeks":            1.0,
}

# Any single expensive keyword above this threshold routes expensive
_EXPENSIVE_THRESHOLD: float = 1.5

# Long messages carry structural complexity regardless of keywords
_LENGTH_EXPENSIVE_CHARS: int = 120


def route_task(user_input: str) -> str:
    """
    Returns 'cheap' or 'expensive'.

    Accumulates weighted scores for matched keywords.  A single expensive
    keyword above threshold, or a long message, routes expensive.
    Only routes cheap when there is a positive cheap signal and zero
    expensive signal.  Defaults to 'expensive' for everything else.
    """
    text = (user_input or "").lower()

    expensive_score: float = sum(
        weight for kw, weight in _EXPENSIVE_KEYWORDS.items() if kw in text
    )

    if expensive_score >= _EXPENSIVE_THRESHOLD:
        return "expensive"

    if len(text) >= _LENGTH_EXPENSIVE_CHARS:
        return "expensive"

    cheap_score: float = sum(
        weight for kw, weight in _CHEAP_KEYWORDS.items() if kw in text
    )

    if cheap_score > 0 and expensive_score == 0:
        return "cheap"

    # Default: stronger model for anything unrecognised
    return "expensive"
