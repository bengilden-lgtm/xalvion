from __future__ import annotations

from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


VALID_QUEUES = {"new", "waiting", "escalated", "refund_risk", "vip", "resolved"}
VALID_STATUSES = {"new", "waiting", "escalated", "resolved", "failed"}
VALID_PRIORITIES = {"low", "medium", "high"}
VALID_RISKS = {"low", "medium", "high"}
VALID_CHANNELS = {"web", "email", "api", "chat", "mobile"}
VALID_SOURCES = {"workspace", "sdk", "api", "webhook", "import"}


def _safe_queue(value: Any, default: str = "new") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_QUEUES else default


def _safe_status(value: Any, default: str = "new") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_STATUSES else default


def _safe_priority(value: Any, default: str = "medium") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_PRIORITIES else default


def _safe_risk(value: Any, default: str = "medium") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_RISKS else default


def _safe_channel(value: Any, default: str = "web") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_CHANNELS else default


def _safe_source(value: Any, default: str = "workspace") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_SOURCES else default


def _clamp(value: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value or 0)))
    except (TypeError, ValueError):
        return lo


def get_plan_name(user: Any | None) -> str:
    if not user:
        return "free"
    tier = (getattr(user, "tier", None) or "free").strip().lower()
    return tier if tier in {"free", "pro", "elite", "dev"} else "free"


def _tier_upgrade_unlocks(tier: str) -> str:
    t = str(tier or "free").strip().lower()
    if t == "free":
        return "500 tickets/month, full dashboard, priority routing"
    if t == "pro":
        return "5,000 tickets/month, advanced analytics, 20 team seats"
    return ""


def normalize_customer_email(value: Any) -> str:
    """Return a trimmed RFC-ish local@domain string, or empty if unusable for delivery."""
    raw = str(value or "").strip()
    if not raw or "@" not in raw:
        return ""
    return raw[:320]


def resolve_customer_email_for_ticket(
    *,
    request_context: dict[str, Any] | None = None,
    customer_email: str | None = None,
) -> str:
    """Prefer ``request_context.sender``, then explicit ``customer_email`` on the support payload."""
    ctx = request_context if isinstance(request_context, dict) else {}
    sender = normalize_customer_email(ctx.get("sender"))
    if sender:
        return sender
    return normalize_customer_email(customer_email)


def _me_capacity_message(tier: str, remaining: int) -> str:
    t = str(tier or "free").strip().lower()
    if t == "elite":
        return "Elite tier — full capacity"
    if t == "pro":
        return f"Pro tier — {remaining} tickets remaining"
    return f"Free tier — {remaining} tickets left this month"

