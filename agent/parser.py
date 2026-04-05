from __future__ import annotations

import json
from typing import Any, Dict


def parse_llm_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    fallback = text or "I’ve reviewed this and I’m already on the next step."
    return {
        "customer_message": fallback,
        "action": "none",
        "amount": 0,
        "reason": "fallback_parse",
        "confidence": 0.45,
        "risk_level": "medium",
        "internal_note": "Fallback parse path used.",
        "customer_note": fallback,
        "queue": "new",
        "priority": "medium",
    }


def clamp_confidence(value: Any, fallback: float = 0.9) -> float:
    try:
        number = float(value)
    except Exception:
        number = fallback

    if number <= 0:
        number = fallback

    if number < 0.55:
        number = 0.55
    if number > 0.99:
        number = 0.99

    return round(number, 2)
