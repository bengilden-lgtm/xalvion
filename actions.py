from __future__ import annotations

from typing import Any, Dict, List


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def classify_issue(issue: str) -> str:
    text = (issue or "").lower()

    if "charged twice" in text or "double charge" in text or "billed twice" in text:
        return "billing_duplicate_charge"
    if "refund" in text:
        return "refund_request"
    if "late" in text or "where is my order" in text or "tracking" in text or "package" in text:
        return "shipping_issue"
    if "damaged" in text or "broken" in text:
        return "damaged_order"
    if "login" in text or "password" in text or "sign in" in text:
        return "auth_issue"
    if "export" in text and "error" in text:
        return "export_error"

    return "general_support"


def build_ticket(message: str, user_id: str = "anonymous", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = meta or {}

    ticket = {
        "customer": user_id,
        "user_id": user_id,
        "issue": (message or "").strip(),
        "ltv": _to_int(meta.get("ltv", 0), 0),
        "sentiment": _to_int(meta.get("sentiment", 5), 5),
        "order_status": meta.get("order_status", "unknown"),
        "issue_type": classify_issue(message or ""),
    }

    return ticket


def system_decision(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hard non-LLM business rules.
    These always run first.
    """
    ticket = ticket or {}
    issue = str(ticket.get("issue", "")).lower()
    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _to_int(ticket.get("sentiment", 5), 5)
    ltv = _to_int(ticket.get("ltv", 0), 0)

    # Billing duplicate charge = deterministic action
    if issue_type == "billing_duplicate_charge" or "charged twice" in issue or "double charge" in issue:
        return {
            "action": "refund",
            "amount": 25,
            "reason": "Duplicate-charge protection policy",
            "priority": "high",
        }

    # High-value, very unhappy customer
    if sentiment <= 2 and ltv >= 500:
        return {
            "action": "refund",
            "amount": min(max(int(ltv * 0.10), 20), 50),
            "reason": "High-LTV recovery",
            "priority": "high",
        }

    # Damaged order + negative sentiment
    if issue_type == "damaged_order" and sentiment <= 4:
        return {
            "action": "credit",
            "amount": 20,
            "reason": "Damaged-order recovery",
            "priority": "high",
        }

    # Shipping issue + upset customer
    if issue_type == "shipping_issue" and sentiment <= 3:
        return {
            "action": "credit",
            "amount": 15,
            "reason": "Shipping frustration recovery",
            "priority": "medium",
        }

    # Refund request but not yet approved automatically
    if issue_type == "refund_request":
        return {
            "action": "review",
            "amount": 0,
            "reason": "Refund request needs context review",
            "priority": "medium",
        }

    return {
        "action": "none",
        "amount": 0,
        "reason": "No hard-rule action triggered",
        "priority": "normal",
    }


def apply_learned_rules(ticket: Dict[str, Any], learned_rules: List[Dict[str, Any]] | None) -> Dict[str, Any] | None:
    """
    Applies learned rules after hard rules.
    Rule format:
    {
        "trigger": "low_sentiment_shipping",
        "condition": {"issue_type": "shipping_issue", "sentiment_lte": 3},
        "action": {"type": "credit", "amount": 10}
    }
    """
    if not learned_rules:
        return None

    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _to_int(ticket.get("sentiment", 5), 5)
    ltv = _to_int(ticket.get("ltv", 0), 0)

    for rule in learned_rules:
        cond = rule.get("condition", {})
        action = rule.get("action", {})

        issue_ok = cond.get("issue_type") in (None, issue_type)
        sentiment_ok = sentiment <= _to_int(cond.get("sentiment_lte", 10), 10)
        ltv_ok = ltv >= _to_int(cond.get("ltv_gte", 0), 0)

        if issue_ok and sentiment_ok and ltv_ok:
            return {
                "action": action.get("type", "none"),
                "amount": _to_int(action.get("amount", 0), 0),
                "reason": f"Learned rule: {rule.get('trigger', 'unknown_rule')}",
                "priority": "medium",
            }

    return None


def calculate_impact(ticket: Dict[str, Any], executed_action: Dict[str, Any]) -> Dict[str, Any]:
    action = executed_action.get("action", "none")
    amount = _to_int(executed_action.get("amount", 0), 0)

    if action == "refund":
        return {"type": "refund", "amount": amount}
    if action == "credit":
        return {"type": "credit", "amount": amount}
    if action == "review":
        return {"type": "saved", "amount": 15}

    return {"type": "saved", "amount": 50}