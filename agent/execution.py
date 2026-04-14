from __future__ import annotations

import os
from typing import Any, Dict

from actions import (
    MAX_AUTO_CREDIT_AMOUNT,
    MAX_AUTO_REFUND_AMOUNT,
    HANDLED_ISSUE_TYPES,
    execute_action as dispatch_integrated_action,
    execution_requires_operator_gate,
)
from governor import normalize_plan_tier, plan_limits
from tools import execute_tool

ALLOWED_ACTIONS = {"none", "refund", "credit", "review", "charge"}
# Legacy module-level caps (charges use bounded proposal amounts).
MAX_REFUND = int(MAX_AUTO_REFUND_AMOUNT)
MAX_CHARGE = int(MAX_AUTO_REFUND_AMOUNT)
MAX_CREDIT = int(MAX_AUTO_CREDIT_AMOUNT)


def should_attach_order_context(issue_type: str) -> bool:
    return issue_type in HANDLED_ISSUE_TYPES and issue_type in {"shipping_issue", "damaged_order"}


def normalize_action_payload(payload: Dict[str, Any] | None, *, plan_tier: str | None = None) -> Dict[str, Any]:
    payload = payload or {}
    action = str(payload.get("action", "none")).strip().lower()
    amount = int(payload.get("amount", 0) or 0)

    if action not in ALLOWED_ACTIONS:
        action = "none"

    if amount < 0:
        amount = 0

    tier = normalize_plan_tier(plan_tier or "free")
    limits = plan_limits(tier)
    max_cred = max(0, int(float(limits.get("max_credit") or 0)))

    if action == "refund":
        # Do not clamp here: tier limits are enforced by ``execution_requires_operator_gate``,
        # ``governor.validate_decision``, and payment backends. Clamping would distort approval UX.
        pass
    elif action == "credit":
        cap = max_cred if max_cred > 0 else MAX_CREDIT
        amount = min(amount, cap)
    elif action == "charge":
        amount = min(amount, MAX_CHARGE)
    else:
        amount = 0

    return {
        "action": action,
        "amount": amount,
        "reason": str(payload.get("reason", "") or ""),
        "priority": str(payload.get("priority", "medium") or "medium"),
        "risk_level": str(payload.get("risk_level", "medium") or "medium"),
        "queue": str(payload.get("queue", "new") or "new"),
        "requires_approval": bool(payload.get("requires_approval", False)),
    }


def execute_action(ticket: Dict[str, Any], action_payload: Dict[str, Any]) -> Dict[str, Any]:
    _tier = str(ticket.get("plan_tier", "free") or "free")
    safe_action = dict(normalize_action_payload(action_payload, plan_tier=_tier))
    if execution_requires_operator_gate(
        safe_action["action"],
        safe_action["amount"],
        plan_tier=_tier,
    ):
        safe_action["requires_approval"] = True
    action = safe_action["action"]
    amount = safe_action["amount"]

    if safe_action.get("requires_approval"):
        result = {
            "status": "pending_approval",
            "type": "approval_gate",
            "message": "Action held for approval",
            "proposed_action": action,
            "proposed_amount": amount,
        }
        return {
            "action": action,
            "amount": amount,
            "tool_result": result,
            "tool_status": str(result["status"]),
        }

    request_context = ticket.get("request_context") or {}
    customer_email = str(ticket.get("customer_email") or request_context.get("sender") or "").strip()
    if customer_email and "@" not in customer_email:
        customer_email = ""

    payload: Dict[str, Any] = {
        "customer": ticket.get("customer", "Unknown"),
        "customer_name": ticket.get("customer", "there"),
        "customer_email": customer_email,
        "message": str(ticket.get("issue", "") or ""),
        "issue_type": str(ticket.get("issue_type", "general_support") or "general_support"),
        "source": str(ticket.get("source", "workspace") or "workspace"),
        "priority": str(safe_action.get("priority", "medium") or "medium"),
        "amount": amount,
        "status": str(ticket.get("order_status", "unknown") or "unknown"),
        "order_status": str(ticket.get("order_status", "unknown") or "unknown"),
        "tracking_id": str(ticket.get("tracking", "") or ""),
        "tracking_url": str(ticket.get("tracking_url", "") or ""),
        "eta": str(ticket.get("eta", "") or ""),
        "carrier": str(ticket.get("carrier", "") or ""),
        "order_id": str(ticket.get("order_id", "") or ""),
    }

    if action == "refund":
        result = execute_tool("refund", payload)
        if result.get("error"):
            return {"action": "review", "amount": 0, "tool_result": result, "tool_status": result.get("error", "error")}
        exec_mode = (os.getenv("XALVION_EXEC_MODE", "mock") or "mock").strip().lower()
        is_mock = exec_mode != "live"
        # FIX 7: Simulated/mock executions must never report verified_success=True or status="success".
        if is_mock:
            result = {**result, "mock": True, "verified": False, "verified_success": False, "status": "simulated", "is_simulated": True}
        else:
            result = {**result, "mock": False, "verified": True, "is_simulated": False}
        tool_status = "simulated" if is_mock else result.get("status", "success")
        return {"action": "refund", "amount": amount, "tool_result": result, "tool_status": tool_status}

    if action == "credit":
        result = execute_tool("credit", payload)
        EXEC_MODE = (os.getenv("XALVION_EXEC_MODE", "mock") or "mock").strip().lower()
        verified = EXEC_MODE == "live"
        is_mock = not verified
        # FIX 7: Simulated/mock executions must never report verified_success=True or status="success".
        if is_mock:
            result = {**result, "verified": False, "mock": True, "verified_success": False, "status": "simulated", "is_simulated": True}
        else:
            result = {**result, "verified": True, "mock": False, "is_simulated": False}
        tool_status = "simulated" if is_mock else result.get("status", "credit_issued")
        return {"action": "credit", "amount": amount, "tool_result": result, "tool_status": tool_status}

    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")

    # Standard shipping / damage — never hit integration dispatch (including charge).
    if issue_type == "shipping_issue":
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_tracking", "type": "tracking", "message": "Shipping handled locally"},
            "tool_status": "local_tracking",
        }

    if issue_type == "damaged_order":
        return {
            "action": "review",
            "amount": 0,
            "tool_result": {"status": "local_damage_flow", "type": "escalation", "message": "Damage routed locally"},
            "tool_status": "local_damage_flow",
        }

    if issue_type in {"billing_duplicate_charge", "billing_issue", "payment_issue"}:
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_billing_flow", "type": "billing", "message": "Billing handled locally"},
            "tool_status": "local_billing_flow",
        }

    if issue_type == "refund_request":
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_refund_request", "type": "billing", "message": "Refund request handled locally"},
            "tool_status": "local_refund_request",
        }

    if action == "charge":
        integration_result = dispatch_integrated_action("charge", payload)
        return {"action": "charge", "amount": amount, "tool_result": integration_result, "tool_status": integration_result.get("status", "manual_charge_required")}

    integrated_action = "escalate" if action == "review" else action
    integration_result = dispatch_integrated_action(integrated_action, payload)
    mapped_action = "review" if integrated_action == "escalate" else action

    return {
        "action": mapped_action,
        "amount": amount if mapped_action in {"refund", "credit", "charge"} else 0,
        "tool_result": integration_result,
        "tool_status": integration_result.get("status", "success"),
    }
