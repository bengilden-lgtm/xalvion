"""
agent/formatters.py — Pure string formatting helpers extracted from response_builder.
No dependencies on other agent modules. Safe to import anywhere.
"""
from __future__ import annotations

from typing import Any, Dict


def classify_tone(ticket: Dict[str, Any]) -> str:
    sentiment = int(ticket.get("sentiment", 5) or 5)
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    operator_mode = str(ticket.get("operator_mode", "balanced") or "balanced")

    if operator_mode == "fraud_aware":
        return "firm_precise"
    if operator_mode == "delight":
        return "warm_premium"
    if sentiment <= 2:
        return "high_empathy"
    if issue_type in {"billing_duplicate_charge", "damaged_order"}:
        return "calm_action"
    if issue_type == "shipping_issue":
        return "clear_reassuring"
    return "premium_direct"


def polish_message(message: str) -> str:
    text = (message or "").strip()

    replacements = {
        "I understand your concern about": "I checked",
        "I understand your concern regarding": "I checked",
        "I understand that": "I checked that",
        "Please let me know if you need further assistance.": "",
        "please let me know if you need further assistance.": "",
        "If you need further assistance, please let me know.": "",
        "If you need further assistance, let me know.": "",
        "currently": "",
        "Currently, ": "",
        "currently, ": "",
        "We appreciate your patience.": "",
        "Thank you for your patience.": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "  " in text:
        text = text.replace("  ", " ")

    text = text.replace("..", ".").strip()
    return text


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return "" if text is None else str(text)

    # Try common mojibake repair paths. Running more than once helps when a
    # string has been mis-decoded repeatedly through different layers.
    repair_attempts = (
        ("latin1", "utf-8"),
        ("cp1252", "utf-8"),
    )
    for _ in range(2):
        changed = False
        for src_enc, dst_enc in repair_attempts:
            try:
                repaired = text.encode(src_enc).decode(dst_enc)
                if repaired != text:
                    text = repaired
                    changed = True
                    break
            except Exception:
                continue
        if not changed:
            break

    replacements = {
        "Iâve": "I’ve",
        "Iâ€™ve": "I’ve",
        "Iâve": "I’ve",
        "â€™": "’",
        "â": "’",
        "â€˜": "‘",
        "â": "‘",
        "â€œ": "“",
        "â": "“",
        "â€�": "”",
        "â": "”",
        "â€“": "–",
        "â": "–",
        "â€”": "—",
        "â": "—",
        "â€¦": "…",
        "â¦": "…",
        "Â ": " ",
        "Â": "",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text


def is_conversational_message(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True

    conversational_exact = {
        "hi", "hello", "hey", "heya", "yo", "sup", "wassup", "what's up", "whats up",
        "how are you", "how r u", "how are u", "who are you", "who are u", "thanks", "thank you", "thx", "cool", "nice",
    }

    if text in conversational_exact:
        return True

    support_markers = (
        "order", "package", "refund", "charged", "billing", "damaged", "late", "tracking",
        "delivered", "not working", "error", "invoice", "login", "password", "export",
        "cancel", "cancelling", "canceling", "shipping", "address", "change my shipping address",
        "double charge", "duplicate charge", "arrived", "delay", "delayed", "broken",
    )
    if any(marker in text for marker in support_markers):
        return False

    if "i'm cancel" in text or "im cancel" in text:
        return False

    return len(text.split()) <= 4

