"""
utils.py — safe helpers and ticket normalizer.

KEY FIX: The old normalize_ticket() stripped issue_type, operator_mode,
plan_tier, and customer_history before they reached system_decision(),
so all triage logic silently misfired.  This version preserves every
field actions.py depends on.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict


def safe_str(value: Any, default: str = "") -> str:
    try:
        if isinstance(value, str):
            return value
        return str(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitise + enrich a raw ticket dict.

    Preserves every key that actions.py / agent.py rely on:
      issue_type, operator_mode, plan_tier, customer_history, triage, …
    """
    base = {
        # Core identity
        "customer":         safe_str(ticket.get("customer", "Unknown")),
        "user_id":          safe_str(ticket.get("user_id", ticket.get("customer", "Unknown"))),
        "issue":            safe_str(ticket.get("issue", "")),
        "ltv":              safe_int(ticket.get("ltv", 0)),
        "sentiment":        max(1, min(10, safe_int(ticket.get("sentiment", 5)))),
        "timestamp":        safe_str(ticket.get("timestamp", "")),
        # Routing / enrichment (MUST be preserved)
        "issue_type":       safe_str(ticket.get("issue_type", "general_support")),
        "operator_mode":    safe_str(ticket.get("operator_mode", "balanced")),
        "plan_tier":        safe_str(ticket.get("plan_tier", "free")),
        "order_status":     safe_str(ticket.get("order_status", "unknown")),
        "channel":          safe_str(ticket.get("channel", "web")),
        "source":           safe_str(ticket.get("source", "workspace")),
        # History object (dict, not stripped)
        "customer_history": ticket.get("customer_history") or {},
        # Pre-computed triage (kept if already present)
        "triage":           ticket.get("triage") or {},
    }
    return base


def safe_execute(func, *args, **kwargs) -> Any:
    """Call func(*args, **kwargs), catch any exception, log it, return error dict."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        print("\n🚨 SYSTEM ERROR CAUGHT:")
        print(str(exc))
        traceback.print_exc()
        return {"__xalvion_exec_error__": True, "error": str(exc)}
