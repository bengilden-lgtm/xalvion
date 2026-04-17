from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import governor as governor_mod

logger = logging.getLogger("xalvion.exec")


SUPPORTED_LIVE_ACTIONS = {"refund"}


@dataclass(frozen=True)
class ExecutionDecision:
    governor_decision: str  # allow | review | block
    governor_result: Dict[str, Any]


def _decision_from_governor(*, governor_result: dict, human_approved: bool) -> str:
    mode = str((governor_result or {}).get("execution_mode", "") or "").strip().lower()
    if mode == "blocked":
        return "block"
    if mode == "auto":
        return "allow"
    # review / unknown
    return "allow" if human_approved else "review"


def evaluate_governor(
    *,
    ticket: Dict[str, Any],
    proposed_action: Dict[str, Any],
    memory: Optional[Dict[str, Any]] = None,
    human_approved: bool = False,
) -> ExecutionDecision:
    gov_result = governor_mod.gate_execution(ticket or {}, proposed_action or {}, memory or {})
    governor_decision = _decision_from_governor(governor_result=gov_result, human_approved=human_approved)
    return ExecutionDecision(governor_decision=governor_decision, governor_result=gov_result)


def execute_action(
    *,
    ticket: Dict[str, Any],
    proposed_action: Dict[str, Any],
    memory: Optional[Dict[str, Any]] = None,
    human_approved: bool = False,
    execution_mode: str = "live",
    stripe_user: Any = None,
    stripe_req: Any = None,
) -> Dict[str, Any]:
    """
    Single authoritative execution boundary for real customer-impacting actions.

    Contract:
    - Governor is absolute: if governor_decision != "allow", NO real execution occurs.
    - Strict mode (refund-first): only refunds may execute in live mode.
    - Returns a normalized execution payload with lifecycle-ish fields.
    """
    action = str((proposed_action or {}).get("action", "none") or "none").strip().lower()
    amount = float((proposed_action or {}).get("amount", 0) or 0)
    execution_mode = str(execution_mode or "live").strip().lower()

    decision = evaluate_governor(
        ticket=ticket or {},
        proposed_action={"action": action, "amount": amount, **(proposed_action or {})},
        memory=memory or {},
        human_approved=human_approved,
    )

    logger.info(
        "governor_decision action=%s amount=%s decision=%s mode=%s reason=%s risk=%s score=%s",
        action,
        round(amount, 2),
        decision.governor_decision,
        str((decision.governor_result or {}).get("execution_mode", "") or ""),
        str((decision.governor_result or {}).get("governor_reason", "") or "")[:300],
        str((decision.governor_result or {}).get("governor_risk_level", "") or ""),
        int((decision.governor_result or {}).get("governor_risk_score", 0) or 0),
    )

    if execution_mode != "live":
        return {
            "ok": True,
            "lifecycle": "executed",
            "action": action,
            "amount": amount,
            "tool_status": "simulated",
            "tool_result": {
                "status": "simulated",
                "is_simulated": True,
                "verified": False,
                "verified_success": False,
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            },
            "is_simulated": True,
            "verified_success": False,
            "governor_decision": decision.governor_decision,
            "governor": decision.governor_result,
        }

    if decision.governor_decision != "allow":
        return {
            "ok": False,
            "lifecycle": "requires_approval" if decision.governor_decision == "review" else "failed",
            "action": action,
            "amount": amount,
            "tool_status": "pending_approval" if decision.governor_decision == "review" else "blocked",
            "tool_result": {
                "status": "pending_approval" if decision.governor_decision == "review" else "blocked",
                "message": str(decision.governor_result.get("governor_reason") or "Blocked under governor policy."),
                "violations": list(decision.governor_result.get("violations") or []),
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            },
            "is_simulated": False,
            "verified_success": False,
            "governor_decision": decision.governor_decision,
            "governor": decision.governor_result,
        }

    # Governor allow => strict live support checks
    if action not in SUPPORTED_LIVE_ACTIONS:
        return {
            "ok": False,
            "lifecycle": "failed",
            "action": action,
            "amount": amount,
            "tool_status": "not_supported",
            "tool_result": {
                "status": "not_supported",
                "message": "Not supported in live execution yet",
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            },
            "is_simulated": False,
            "verified_success": False,
            "governor_decision": decision.governor_decision,
            "governor": decision.governor_result,
        }

    if action == "refund":
        if stripe_user is None or stripe_req is None:
            return {
                "ok": False,
                "lifecycle": "failed",
                "action": action,
                "amount": amount,
                "tool_status": "missing_payment_reference",
                "tool_result": {
                    "status": "missing_payment_reference",
                    "message": "payment_intent_id or charge_id required.",
                    "governor_decision": decision.governor_decision,
                    "governor": decision.governor_result,
                },
                "is_simulated": False,
                "verified_success": False,
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            }

        from services import stripe_service

        logger.info("execution_start action=refund amount=%s human_approved=%s", round(amount, 2), bool(human_approved))
        refund_result = stripe_service.execute_real_refund(
            amount=int(amount or 0),
            payment_intent_id=getattr(stripe_req, "payment_intent_id", None),
            charge_id=getattr(stripe_req, "charge_id", None),
            refund_reason=getattr(stripe_req, "refund_reason", None),
            username=str(getattr(stripe_user, "username", "unknown") or "unknown"),
            issue_type=str((ticket or {}).get("issue_type", "general_support") or "general_support"),
            user=stripe_user,
            result={"action": "refund", "amount": amount, **(proposed_action or {})},
        )
        logger.info(
            "execution_result action=refund ok=%s status=%s detail=%s",
            bool(refund_result.get("ok")),
            str(refund_result.get("status", "") or ""),
            str(refund_result.get("detail", "") or "")[:300],
        )

        if refund_result.get("ok"):
            refunded_amount = float(refund_result.get("amount", amount) or amount)
            return {
                "ok": True,
                "lifecycle": "executed",
                "action": "refund",
                "amount": refunded_amount,
                "tool_status": "refunded",
                "tool_result": {**refund_result, "verified": True, "mock": False},
                "is_simulated": False,
                "verified_success": True,
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            }

        return {
            "ok": False,
            "lifecycle": "failed",
            "action": "refund",
            "amount": 0.0,
            "tool_status": str(refund_result.get("status", "refund_failed") or "refund_failed"),
            "tool_result": {
                **(refund_result if isinstance(refund_result, dict) else {"raw": refund_result}),
                "verified": False,
                "verified_success": False,
                "governor_decision": decision.governor_decision,
                "governor": decision.governor_result,
            },
            "is_simulated": False,
            "verified_success": False,
            "governor_decision": decision.governor_decision,
            "governor": decision.governor_result,
        }

    # Defensive default (shouldn't happen given strict support set)
    return {
        "ok": False,
        "lifecycle": "failed",
        "action": action,
        "amount": 0.0,
        "tool_status": "not_supported",
        "tool_result": {"status": "not_supported", "message": "Not supported in live execution yet"},
        "is_simulated": False,
        "verified_success": False,
        "governor_decision": decision.governor_decision,
        "governor": decision.governor_result,
    }
