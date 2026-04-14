from __future__ import annotations

"""
plan_config.py — Plan tier display config and upgrade payload builder.

Owns:
  - PLAN_CONFIG (monthly limits, labels, feature flags per tier)
  - get_plan_config(), get_public_plan_name(), get_plan_name(), monthly_ticket_limit_for_plan(), build_upgrade_payload()

Does NOT own:
  - Financial policy limits (max_refund, can_auto_refund) — see governor.py
  - Stripe price IDs — see app.py config constants

Imports from:
  - app_utils (get_plan_name)
"""

from typing import Any


PLAN_CONFIG: dict[str, dict[str, Any]] = {
    "free": {
        "monthly_limit": 12,
        "history_limit": 20,
        "streaming": True,
        "dashboard_access": "basic",
        "priority_routing": False,
        "team_seats": 1,
        "label": "Free",
    },
    "pro": {
        "monthly_limit": 500,
        "history_limit": 500,
        "streaming": True,
        "dashboard_access": "full",
        "priority_routing": True,
        "team_seats": 3,
        "label": "Pro",
    },
    "elite": {
        "monthly_limit": 5000,
        "history_limit": 5000,
        "streaming": True,
        "dashboard_access": "advanced",
        "priority_routing": True,
        "team_seats": 20,
        "label": "Elite",
    },
    "dev": {
        "monthly_limit": 10**9,
        "history_limit": 10**9,
        "streaming": True,
        "dashboard_access": "advanced",
        "priority_routing": True,
        "team_seats": 999,
        "label": "Dev",
    },
}


PUBLIC_PLAN_TIERS = {"free", "pro", "elite"}


def get_plan_name(user: Any) -> str:
    from app_utils import get_plan_name as _get_plan_name

    return _get_plan_name(user)


def get_public_plan_name(user: Any | None) -> str:
    tier = get_plan_name(user)
    return tier if tier in PUBLIC_PLAN_TIERS else "free"


def get_plan_config(tier: str | None) -> dict[str, Any]:
    return PLAN_CONFIG.get((tier or "free").strip().lower(), PLAN_CONFIG["free"])


def monthly_ticket_limit_for_plan(plan_name: str) -> int:
    """Canonical monthly ticket cap from ``governor.plan_limits`` (falls back to ``PLAN_CONFIG``)."""
    from governor import normalize_plan_tier, plan_limits

    raw = plan_limits(normalize_plan_tier(plan_name)).get("monthly_tickets")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(get_plan_config(plan_name)["monthly_limit"])


def build_upgrade_payload(current_tier: str) -> dict[str, Any]:
    import os

    current_key = current_tier if current_tier in PUBLIC_PLAN_TIERS else "free"
    suggestions = ["pro", "elite"] if current_key == "free" else ["elite"] if current_key == "pro" else []

    # Stripe price IDs are owned by app.py config constants; this function only needs to expose a
    # stable boolean for UI gating. Reading the env directly preserves the existing behavior
    # without importing app.py (avoids circular imports / app boot).
    stripe_price_pro = (os.getenv("STRIPE_PRICE_PRO", "") or "").strip()
    stripe_price_elite = (os.getenv("STRIPE_PRICE_ELITE", "") or "").strip()
    price_map = {"pro": stripe_price_pro, "elite": stripe_price_elite}

    return {
        "current_tier": current_key,
        "available_upgrades": suggestions,
        "plans": {
            tier: {
                "label": cfg["label"],
                "monthly_limit": monthly_ticket_limit_for_plan(tier),
                "history_limit": cfg["history_limit"],
                "dashboard_access": cfg["dashboard_access"],
                "priority_routing": cfg["priority_routing"],
                "team_seats": cfg["team_seats"],
                "checkout_ready": bool(price_map.get(tier)),
            }
            for tier, cfg in PLAN_CONFIG.items()
            if tier in PUBLIC_PLAN_TIERS
        },
    }

