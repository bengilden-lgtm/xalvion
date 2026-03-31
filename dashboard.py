"""
dashboard.py — in-process simulation dashboard.

This module was imported by ticket_engine.py but never existed, causing
an ImportError on every simulation run.  Now implemented properly.
"""
from __future__ import annotations

from typing import Any, Dict

_state: Dict[str, Any] = {
    "total_tickets": 0,
    "refunds": 0,
    "credits": 0,
    "saved": 0,
    "auto_resolved": 0,
    "money_moved": 0.0,
    "money_saved": 0.0,
}


def update_dashboard(impact: Dict[str, Any]) -> None:
    """Called after each ticket is processed with the impact dict."""
    if not isinstance(impact, dict):
        return

    _state["total_tickets"] += 1

    impact_type = str(impact.get("type", "none") or "none").lower()
    amount = float(impact.get("amount", 0) or 0)
    money_saved = float(impact.get("money_saved", 0) or 0)
    auto_resolved = bool(impact.get("auto_resolved", False))

    if impact_type == "refund":
        _state["refunds"] += 1
        _state["money_moved"] += amount
    elif impact_type == "credit":
        _state["credits"] += 1
        _state["money_moved"] += amount
        _state["money_saved"] += money_saved
    elif impact_type == "saved":
        _state["saved"] += 1
        _state["money_saved"] += money_saved

    if auto_resolved:
        _state["auto_resolved"] += 1


def show_dashboard() -> None:
    """Print a summary of the current simulation run."""
    total = _state["total_tickets"]
    if total == 0:
        print("\n📊 No tickets processed yet.")
        return

    auto_rate = round(_state["auto_resolved"] / total * 100, 1)

    print("\n" + "=" * 50)
    print("📊  XALVION DASHBOARD")
    print("=" * 50)
    print(f"  Tickets processed : {total}")
    print(f"  Auto-resolved     : {_state['auto_resolved']}  ({auto_rate}%)")
    print(f"  Refunds issued    : {_state['refunds']}")
    print(f"  Credits issued    : {_state['credits']}")
    print(f"  Saved / reviewed  : {_state['saved']}")
    print(f"  Money moved       : ${_state['money_moved']:.2f}")
    print(f"  Value preserved   : ${_state['money_saved']:.2f}")
    print("=" * 50)


def reset_dashboard() -> None:
    """Reset state between simulation runs."""
    for key in _state:
        _state[key] = 0 if isinstance(_state[key], int) else 0.0
