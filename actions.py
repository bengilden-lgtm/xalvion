from __future__ import annotations

import os
from typing import Any, Dict, List

VALID_MODES = {"conservative", "balanced", "delight", "fraud_aware"}

# Authoritative fast-path issue types (workspace + agent must stay aligned).
HANDLED_ISSUE_TYPES = frozenset({
    "shipping_issue",
    "damaged_order",
    "billing_duplicate_charge",
    "billing_issue",
    "payment_issue",
    "refund_request",
})

# IMPORTANT: These constants are fallback defaults for non-tier-aware code paths only.
# governor.py is the authoritative tier-aware source (free: $15, pro: $50, elite: $100).
# When a ticket's plan_tier is known, callers MUST use governor.plan_limits(plan_tier)
# instead of these constants.  See also: TODO in app.approve_ticket_action() and
# agent/execution.execute_action() to pass plan_tier to execution_requires_operator_gate().
MAX_AUTO_REFUND_AMOUNT: float = 50.0
MAX_AUTO_CREDIT_AMOUNT: float = 30.0
MAX_APPROVAL_THRESHOLD: float = 25.0


def execution_requires_operator_gate(action: str, amount: Any) -> bool:
    “””
    Fast-path gate: returns True if the action/amount combo must NOT be auto-executed.

    NOTE: This function uses flat constants (MAX_APPROVAL_THRESHOLD) and is not
    plan-tier-aware.  For tier-aware enforcement, callers should consult
    governor.plan_limits(plan_tier) first and pass plan_tier-derived thresholds.
    TODO: Add optional plan_tier parameter and wire through approve_ticket_action()
    (app.py) and execute_action() (agent/execution.py) once governor consolidation
    is complete.
    “””
    norm = str(action or "none").strip().lower()
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    if norm in {"refund", "charge"}:
        return True
    live = os.getenv("LIVE_MODE", "false").strip().lower() == "true"
    try:
        thresh = float(os.getenv("APPROVAL_THRESHOLD", str(MAX_APPROVAL_THRESHOLD)))
    except (TypeError, ValueError):
        thresh = float(MAX_APPROVAL_THRESHOLD)
    if live and norm == "credit" and value > thresh:
        return True
    return False


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp(value: Any, low: int, high: int, default: int = 0) -> int:
    number = _to_int(value, default)
    if number < low:
        return low
    if number > high:
        return high
    return number


def classify_issue(issue: str) -> str:
    text = (issue or "").lower()

    if (
        "charged twice" in text
        or "double charge" in text
        or "billed twice" in text
        or "duplicate charge" in text
        or "overcharged" in text
        or "over charged" in text
        or "wrong charge" in text
    ):
        return "billing_duplicate_charge"
    if "damaged" in text or "broken" in text:
        return "damaged_order"
    if "refund" in text:
        return "refund_request"
    if "late" in text or "where is my order" in text or "tracking" in text or "package" in text:
        return "shipping_issue"
    if "login" in text or "password" in text or "sign in" in text:
        return "auth_issue"
    if "export" in text and "error" in text:
        return "export_error"

    return "general_support"


def infer_risk_level(ticket: Dict[str, Any], history: Dict[str, Any] | None = None) -> str:
    ticket = ticket or {}
    history = history or {}
    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))

    risk_points = 0
    if issue_type in {"billing_duplicate_charge", "refund_request", "damaged_order"}:
        risk_points += 2
    if sentiment <= 3:
        risk_points += 2
    if ltv >= 800:
        risk_points += 1
    if abuse_score >= 2 or refund_count >= 3:
        risk_points += 2

    if risk_points >= 5:
        return "high"
    if risk_points >= 3:
        return "medium"
    return "low"


def triage_ticket(ticket: Dict[str, Any], history: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ticket = ticket or {}
    history = history or {}
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))
    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    issue_type = str(ticket.get("issue_type", "general_support"))

    urgency = 50
    if sentiment <= 2:
        urgency += 28
    elif sentiment <= 4:
        urgency += 16
    if issue_type in {"billing_duplicate_charge", "damaged_order"}:
        urgency += 18
    elif issue_type == "shipping_issue":
        urgency += 10

    churn_risk = 35
    if sentiment <= 3:
        churn_risk += 25
    if ltv >= 500:
        churn_risk += 20
    if issue_type in {"refund_request", "billing_duplicate_charge"}:
        churn_risk += 10

    refund_likelihood = 10
    if issue_type in {"refund_request", "billing_duplicate_charge"}:
        refund_likelihood += 50
    if issue_type == "damaged_order":
        refund_likelihood += 22
    if sentiment <= 3:
        refund_likelihood += 10

    abuse_likelihood = 5 + min(35, abuse_score * 12) + min(20, refund_count * 5)
    complexity = 25
    if issue_type in {"auth_issue", "export_error"}:
        complexity += 15
    if issue_type in {"refund_request", "billing_duplicate_charge", "damaged_order"}:
        complexity += 20

    urgency = min(99, urgency)
    churn_risk = min(99, churn_risk)
    refund_likelihood = min(99, refund_likelihood)
    abuse_likelihood = min(99, abuse_likelihood)
    complexity = min(99, complexity)

    recommended_owner = "ai"
    if abuse_likelihood >= 50 or complexity >= 70:
        recommended_owner = "senior_operator"
    elif refund_likelihood >= 60:
        recommended_owner = "billing_ops"

    return {
        "urgency": urgency,
        "churn_risk": churn_risk,
        "refund_likelihood": refund_likelihood,
        "abuse_likelihood": abuse_likelihood,
        "complexity": complexity,
        "recommended_owner": recommended_owner,
        "risk_level": infer_risk_level(ticket, history),
    }


def build_ticket(message: str, user_id: str = "anonymous", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = meta or {}
    history = meta.get("customer_history") or {}

    ticket = {
        "customer": user_id,
        "user_id": user_id,
        "issue": (message or "").strip(),
        "ltv": max(0, _to_int(meta.get("ltv", 0), 0)),
        "sentiment": _clamp(meta.get("sentiment", 5), 1, 10, 5),
        "order_status": meta.get("order_status", "unknown"),
        "issue_type": classify_issue(message or ""),
        "plan_tier": str(meta.get("plan_tier", "free") or "free"),
        "operator_mode": str(meta.get("operator_mode", "balanced") or "balanced"),
        "channel": str(meta.get("channel", "web") or "web"),
        "source": str(meta.get("source", "workspace") or "workspace"),
        "customer_history": history,
    }
    ticket["triage"] = triage_ticket(ticket, history)
    return ticket


def _mode_adjust(action: str, amount: int, operator_mode: str, history: Dict[str, Any]) -> tuple[str, int, str | None]:
    operator_mode = (operator_mode or "balanced").strip().lower()
    if operator_mode not in VALID_MODES:
        operator_mode = "balanced"

    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))

    if operator_mode == "conservative":
        if action == "refund":
            return "review", 0, "Conservative mode routed refund for review"
        if action == "credit":
            return "credit", max(5, min(amount, 10)), "Conservative mode reduced automatic credit"

    if operator_mode == "delight":
        if action == "credit":
            return "credit", min(amount + 5, 30), "Delight mode increased retention credit"
        if action == "review":
            return "credit", 10, "Delight mode converted review into service credit"

    if operator_mode == "fraud_aware":
        if abuse_score >= 2 or refund_count >= 3:
            return "review", 0, "Fraud-aware mode detected repeat refund behavior"
        if action == "credit":
            return "credit", max(5, min(amount, 10)), "Fraud-aware mode reduced automatic credit"

    return action, amount, None


def system_decision(ticket: Dict[str, Any]) -> Dict[str, Any]:
    ticket = ticket or {}
    issue = str(ticket.get("issue", "")).lower()
    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    history = ticket.get("customer_history") or {}
    operator_mode = str(ticket.get("operator_mode", "balanced") or "balanced")
    triage = ticket.get("triage") or triage_ticket(ticket, history)
    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))

    base = {
        "action": "none",
        "amount": 0,
        "reason": "No hard-rule action triggered",
        "priority": "normal",
        "risk_level": triage.get("risk_level", "low"),
        "queue": "new",
        "requires_approval": False,
    }

    if abuse_score >= 3:
        base.update({
            "action": "review",
            "reason": "Repeat abuse signals detected",
            "priority": "high",
            "queue": "refund_risk",
        })
        return base

    if refund_count >= 5:
        base.update({
            "action": "review",
            "reason": "Refund count ({}) exceeds safe threshold".format(refund_count),
            "priority": "high",
            "queue": "refund_risk",
        })
        return base

    billing_dup_signals = (
        "charged twice",
        "double charge",
        "duplicate charge",
        "billed twice",
        "overcharged",
        "over charged",
        "wrong charge",
    )
    if issue_type == "billing_duplicate_charge" or any(s in issue for s in billing_dup_signals):
        base.update({
            "action": "refund",
            "amount": 25,
            "reason": "Duplicate-charge protection policy",
            "priority": "high",
            "queue": "refund_risk",
            "requires_approval": bool(abuse_score >= 2),
        })
    elif sentiment <= 2 and ltv >= 500:
        base.update({
            "action": "refund",
            "amount": min(max(int(ltv * 0.10), 20), 50),
            "reason": "High-LTV recovery",
            "priority": "high",
            "queue": "vip",
            "requires_approval": True,
        })
    elif issue_type == "damaged_order" and sentiment <= 4:
        base.update({
            "action": "credit",
            "amount": 20,
            "reason": "Damaged-order recovery",
            "priority": "high",
            "queue": "escalated",
        })
    elif issue_type == "shipping_issue" and sentiment <= 3:
        base.update({
            "action": "credit",
            "amount": 15,
            "reason": "Shipping frustration recovery",
            "priority": "medium",
            "queue": "waiting",
        })
    elif issue_type == "refund_request":
        base.update({
            "action": "review",
            "amount": 0,
            "reason": "Refund request needs context review",
            "priority": "medium",
            "queue": "refund_risk",
        })
    elif triage.get("complexity", 0) >= 70:
        base.update({
            "action": "review",
            "amount": 0,
            "reason": "High-complexity case routed to review",
            "priority": "high",
            "queue": "escalated",
        })

    adjusted_action, adjusted_amount, mode_reason = _mode_adjust(
        str(base.get("action", "none")),
        _to_int(base.get("amount", 0), 0),
        operator_mode,
        history,
    )
    base["action"] = adjusted_action
    base["amount"] = adjusted_amount
    if mode_reason:
        base["reason"] = mode_reason
        if adjusted_action == "review":
            base["queue"] = "refund_risk" if issue_type in {"refund_request", "billing_duplicate_charge"} else "escalated"

    return base


def apply_learned_rules(ticket: Dict[str, Any], learned_rules: List[Dict[str, Any]] | None) -> Dict[str, Any] | None:
    if not learned_rules:
        return None

    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    triage = ticket.get("triage") or {}

    for rule in learned_rules:
        cond = rule.get("condition", {})
        action = rule.get("action", {})

        issue_ok = cond.get("issue_type") in (None, issue_type)
        sentiment_ok = sentiment <= _to_int(cond.get("sentiment_lte", 10), 10)
        ltv_ok = ltv >= _to_int(cond.get("ltv_gte", 0), 0)
        urgency_ok = triage.get("urgency", 0) >= _to_int(cond.get("urgency_gte", 0), 0)

        if issue_ok and sentiment_ok and ltv_ok and urgency_ok:
            chosen_action = str(action.get("type", "none") or "none")
            chosen_amount = _to_int(action.get("amount", 0), 0)
            adjusted_action, adjusted_amount, mode_reason = _mode_adjust(
                chosen_action,
                chosen_amount,
                str(ticket.get("operator_mode", "balanced") or "balanced"),
                ticket.get("customer_history") or {},
            )
            return {
                "action": adjusted_action,
                "amount": adjusted_amount,
                "reason": mode_reason or f"Learned rule: {rule.get('trigger', 'unknown_rule')}",
                "priority": "medium",
                "risk_level": triage.get("risk_level", "medium"),
                "queue": "waiting",
                "requires_approval": adjusted_action == "refund" and adjusted_amount >= 25,
            }

    return None


def calculate_impact(ticket: Dict[str, Any], executed_action: Dict[str, Any]) -> Dict[str, Any]:
    ticket = ticket or {}
    executed_action = executed_action or {}
    action = str(executed_action.get("action", "none") or "none")
    amount = _to_int(executed_action.get("amount", 0), 0)
    triage = ticket.get("triage") or {}

    if action == "refund":
        return {"type": "refund", "amount": amount, "money_saved": 0, "auto_resolved": True}
    if action == "credit":
        recovered = max(10, min(60, amount + 15))
        return {"type": "credit", "amount": amount, "money_saved": recovered, "auto_resolved": True}
    if action == "review":
        return {"type": "saved", "amount": 15, "money_saved": 15, "auto_resolved": False}

    saved = 25
    if triage.get("abuse_likelihood", 0) >= 50:
        saved = 40
    return {"type": "saved", "amount": saved, "money_saved": saved, "auto_resolved": True}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def project_business_impact(
    ticket: Dict[str, Any],
    executed_action: Dict[str, Any],
    *,
    confidence: float | None = None,
) -> Dict[str, Any]:
    """
    Companion to calculate_impact — additive business projection for outcome intelligence.
    All values are heuristic projections for UI / analytics, not accounting truth.

    Fields:
      revenue_at_risk, revenue_saved, churn_risk_delta, refund_cost,
      time_saved (minutes), confidence_band (low/high/point estimates).
    """
    ticket = ticket or {}
    executed_action = executed_action or {}
    triage = ticket.get("triage") or {}
    action = str(executed_action.get("action", "none") or "none").lower()
    amount = _to_float(_to_int(executed_action.get("amount", 0), 0), 0.0)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    churn_risk = float(_clamp(triage.get("churn_risk", 35), 0, 99, 35))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    risk_level = str(triage.get("risk_level", "medium") or "medium").lower()

    # Exposure if the account churns (capped by observed LTV).
    revenue_at_risk = round(min(float(ltv), float(ltv) * (churn_risk / 100.0) * 1.15), 2)

    # Churn-risk delta in percentage points (negative => projected improvement).
    if action == "refund" and amount > 0:
        churn_risk_delta = round(-min(28.0, 10.0 + amount * 0.2), 2)
    elif action == "credit" and amount > 0:
        churn_risk_delta = round(-min(22.0, 8.0 + amount * 0.25), 2)
    elif action == "review":
        churn_risk_delta = round(-min(14.0, 6.0 + max(0, 7 - sentiment)), 2)
    elif action == "charge" and amount > 0:
        churn_risk_delta = round(-min(6.0, 3.0 + amount * 0.02), 2)
    else:
        churn_risk_delta = round(-min(10.0, 4.0 + max(0, 8 - sentiment) * 0.6), 2)

    # Retention / recovery value surfaced (orthogonal to refund_cost).
    if action == "credit" and amount > 0:
        revenue_saved = round(min(float(ltv) * 0.12, amount * 2.2 + 18.0), 2)
    elif action == "refund" and amount > 0:
        revenue_saved = round(min(float(ltv) * 0.06, 12.0 + amount * 0.1), 2)
    else:
        revenue_saved = round(max(0.0, revenue_at_risk * 0.12 + max(0, 9 - sentiment) * 1.8), 2)

    refund_cost = round(amount, 2) if action == "refund" else 0.0

    if action == "review":
        time_saved = 5.0
    elif action in {"refund", "credit", "charge"}:
        time_saved = 14.0
    else:
        time_saved = 9.0
    if int(triage.get("complexity", 0) or 0) >= 65:
        time_saved += 5.0
    time_saved = round(time_saved, 2)

    conf = confidence
    if conf is None:
        conf = 0.88
    conf = _to_float(conf, 0.88)
    conf = max(0.55, min(0.99, conf))
    margin = 0.04 if risk_level == "low" else 0.06 if risk_level == "medium" else 0.09
    confidence_band = {
        "low": round(max(0.5, conf - margin), 3),
        "high": round(min(0.99, conf + margin * 0.65), 3),
        "point": round(conf, 3),
    }

    return {
        "revenue_at_risk": revenue_at_risk,
        "revenue_saved": revenue_saved,
        "churn_risk_delta": churn_risk_delta,
        "refund_cost": refund_cost,
        "time_saved": time_saved,
        "confidence_band": confidence_band,
    }


def build_decision_confidence_breakdown(
    ticket: Dict[str, Any],
    decision: Dict[str, Any],
    memory: Dict[str, Any] | None,
    pattern_expectation: Dict[str, Any] | None,
    outcome_stats: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    Reusable structural confidence breakdown (deterministic, no IO).

    Combines ticket context, memory, learning pattern expectation, and outcome_store aggregates.
    When outcome data is sparse, outcome_fit stays neutral-conservative.
    """
    ticket = ticket or {}
    decision = decision or {}
    memory = memory or {}
    stats = outcome_stats or {}
    pat = pattern_expectation or {}

    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    act = str(decision.get("action", "none") or "none").strip().lower()
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    triage = ticket.get("triage") or {}
    risk_level = str(triage.get("risk_level", "medium") or "medium").strip().lower()
    complexity = _clamp(triage.get("complexity", 40), 0, 99, 40)

    abuse_score = max(0, _to_int(memory.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(memory.get("refund_count", 0), 0))
    review_count = max(0, _to_int(memory.get("review_count", 0), 0))
    complaint_count = max(0, _to_int(memory.get("complaint_count", 0), 0))

    # --- policy_fit: action aligned with issue heuristics (same family as system_decision) ---
    policy_fit = 0.72
    if issue_type == "billing_duplicate_charge" and act == "refund":
        policy_fit = 0.93
    elif issue_type == "damaged_order" and act == "credit":
        policy_fit = 0.90
    elif issue_type == "shipping_issue" and act == "credit":
        policy_fit = 0.86
    elif issue_type == "refund_request" and act == "review":
        policy_fit = 0.91
    elif issue_type == "refund_request" and act == "refund":
        policy_fit = 0.52
    elif act == "none":
        policy_fit = 0.78 if complexity < 68 else 0.62
    elif act == "review":
        policy_fit = 0.84
    elif act in {"credit", "refund"}:
        policy_fit = 0.74
    elif act == "charge":
        policy_fit = 0.48

    if risk_level == "high":
        policy_fit = round(max(0.25, policy_fit - 0.12), 4)
    elif risk_level == "medium":
        policy_fit = round(max(0.30, policy_fit - 0.04), 4)

    # --- memory_fit: penalize repeat risk, reward stable-ish history ---
    memory_fit = 1.0
    memory_fit -= min(0.42, abuse_score * 0.11)
    memory_fit -= min(0.22, refund_count * 0.055)
    memory_fit -= min(0.12, review_count * 0.035)
    memory_fit -= min(0.14, max(0, complaint_count - 2) * 0.028)
    if sentiment <= 3:
        memory_fit -= 0.06
    memory_fit = round(max(0.28, min(0.98, memory_fit)), 4)

    # --- outcome_fit from logged outcomes + pattern EMA ---
    n = max(0, _to_int(stats.get("similar_case_count", 0), 0))
    sr = stats.get("historical_success_rate")
    rr = stats.get("historical_reopen_rate")
    fail_r = stats.get("failure_rate")
    rev_r = stats.get("reverse_rate")
    disp_r = stats.get("dispute_rate")

    outcome_fit = 0.76
    if n >= 5:
        base = 0.48
        if sr is not None:
            base += float(sr) * 0.44
        if rr is not None:
            base -= float(rr) * 0.62
        if rev_r is not None:
            base -= float(rev_r) * 0.78
        if disp_r is not None:
            base -= float(disp_r) * 0.72
        if fail_r is not None:
            base -= max(0.0, float(fail_r) - 0.12) * 0.35
        # Reward clean auto-stable history when measurable
        if (
            sr is not None
            and rr is not None
            and rev_r is not None
            and disp_r is not None
            and float(sr) >= 0.87
            and float(rr) <= 0.07
            and float(rev_r) <= 0.02
            and float(disp_r) <= 0.02
        ):
            base += 0.10
        outcome_fit = round(max(0.22, min(0.97, base)), 4)
    elif n > 0:
        outcome_fit = 0.74

    exp = str(pat.get("expectation") or "").strip().lower()
    if exp == "high":
        outcome_fit = round(min(0.97, outcome_fit + 0.06), 4)
    elif exp == "low":
        outcome_fit = round(max(0.22, outcome_fit - 0.10), 4)

    band = str(stats.get("outcome_confidence_band") or "medium").strip().lower()
    if band == "low" and n >= 5:
        outcome_fit = round(max(0.22, outcome_fit - 0.12), 4)
    elif band == "high" and n >= 8:
        outcome_fit = round(min(0.97, outcome_fit + 0.05), 4)

    # --- execution_risk: higher = riskier motion (not a "fit" — inverted in overall) ---
    amt = max(0.0, _to_float(_to_int(decision.get("amount", 0), 0), 0.0))
    execution_risk = 0.22
    if act == "charge":
        execution_risk = 0.92
    elif act == "refund":
        execution_risk = 0.62 + min(0.28, amt / 120.0)
    elif act == "credit":
        execution_risk = 0.38 + min(0.30, amt / 90.0)
    elif act == "review":
        execution_risk = 0.28
    elif act == "none":
        execution_risk = 0.20
    if risk_level == "high":
        execution_risk = round(min(0.98, execution_risk + 0.14), 4)
    elif risk_level == "medium":
        execution_risk = round(min(0.98, execution_risk + 0.06), 4)

    # Conservative aggregate: multiplicative dampening by execution risk
    core = min(policy_fit, memory_fit, outcome_fit)
    overall_confidence = round(
        max(0.24, min(0.96, core * (1.0 - 0.38 * execution_risk))),
        4,
    )

    return {
        "policy_fit": round(float(policy_fit), 4),
        "memory_fit": round(float(memory_fit), 4),
        "outcome_fit": round(float(outcome_fit), 4),
        "execution_risk": round(float(execution_risk), 4),
        "overall_confidence": float(overall_confidence),
    }


def blend_llm_and_structural_confidence(
    llm_confidence: Any,
    breakdown: Dict[str, Any] | None,
    similar_case_count: int,
) -> float:
    """
    Merge LLM-reported confidence with structural overall_confidence.
    Never increases above the LLM value; pulls down when history is strong and negative.
    Sparse outcome data barely moves the needle.
    """
    try:
        llm_c = float(llm_confidence)
    except (TypeError, ValueError):
        llm_c = 0.9
    llm_c = max(0.55, min(0.99, llm_c))

    bd = breakdown or {}
    try:
        struct = float(bd.get("overall_confidence", llm_c))
    except (TypeError, ValueError):
        struct = llm_c
    struct = max(0.24, min(0.96, struct))

    n = max(0, int(similar_case_count))
    if n >= 14:
        w = 0.58
    elif n >= 9:
        w = 0.48
    elif n >= 6:
        w = 0.36
    else:
        w = 0.12

    blended = (1.0 - w) * llm_c + w * struct
    # Hard cap by structural when we have enough real cases and structure is cautious
    if n >= 6 and struct < 0.66:
        blended = min(blended, max(struct, 0.52))
    blended = min(blended, llm_c)
    return round(max(0.55, min(0.99, blended)), 4)


def merge_impact_with_business_projection(
    ticket: Dict[str, Any],
    executed_action: Dict[str, Any],
    *,
    confidence: float | None = None,
) -> Dict[str, Any]:
    """
    Non-breaking merge: preserves calculate_impact keys and adds business projection fields.
    Also sets agent_minutes_saved when absent (aligned with time_saved).
    """
    base = calculate_impact(ticket, executed_action)
    biz = project_business_impact(ticket, executed_action, confidence=confidence)
    out: Dict[str, Any] = {**base, **biz}
    if "agent_minutes_saved" not in out or int(out.get("agent_minutes_saved") or 0) == 0:
        out["agent_minutes_saved"] = int(round(float(biz.get("time_saved", 0.0) or 0.0)))
    return out

# ===== ACTION EXECUTION LAYER (NO DOWNGRADE) =====

def execute_action(action_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = payload or {}
    action = str(action_type or "noop").strip().lower()

    try:
        if action == "refund":
            return handle_refund(payload)
        if action == "credit":
            return handle_credit(payload)
        if action == "send_tracking":
            return handle_tracking(payload)
        if action == "escalate":
            return handle_escalation(payload)
        if action == "charge":
            return handle_charge(payload)
        if action in {"noop", "none"}:
            return {
                "status": "no_action",
                "type": "noop",
                "message": "No direct action executed.",
            }
        return {
            "status": "unknown_action",
            "type": action,
            "message": f"Unknown action '{action}' was not executed.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "type": action,
            "error": str(exc),
            "message": f"Action execution failed for '{action}'.",
        }


def handle_refund(payload: Dict[str, Any]) -> Dict[str, Any]:
    amount = _to_int(payload.get("amount", 0), 0)
    customer = str(payload.get("customer", "unknown") or "unknown")
    return {
        "status": "success",
        "type": "refund",
        "customer": customer,
        "amount": amount,
        "message": f"Refund path executed for {customer}."
    }


def handle_credit(payload: Dict[str, Any]) -> Dict[str, Any]:
    amount = _to_int(payload.get("amount", 0), 0)
    customer = str(payload.get("customer", "unknown") or "unknown")
    return {
        "status": "success",
        "type": "credit",
        "customer": customer,
        "amount": amount,
        "message": f"Service credit issued for {customer}."
    }


def handle_tracking(payload: Dict[str, Any]) -> Dict[str, Any]:
    tracking_id = str(payload.get("tracking_id", "TRK-DEV") or "TRK-DEV")
    eta = str(payload.get("eta", "") or "")
    customer = str(payload.get("customer", "unknown") or "unknown")
    message = f"Tracking sent to {customer}: {tracking_id}"
    if eta:
        message += f" · ETA {eta}"
    return {
        "status": "success",
        "type": "send_tracking",
        "customer": customer,
        "tracking_id": tracking_id,
        "eta": eta,
        "message": message,
    }


def handle_escalation(payload: Dict[str, Any]) -> Dict[str, Any]:
    priority = str(payload.get("priority", "normal") or "normal")
    queue = str(payload.get("queue", "escalated") or "escalated")
    customer = str(payload.get("customer", "unknown") or "unknown")
    return {
        "status": "success",
        "type": "escalate",
        "customer": customer,
        "priority": priority,
        "queue": queue,
        "message": f"Case escalated for {customer} with {priority} priority.",
    }


def handle_charge(payload: Dict[str, Any]) -> Dict[str, Any]:
    amount = _to_int(payload.get("amount", 0), 0)
    customer = str(payload.get("customer", "unknown") or "unknown")
    return {
        "status": "pending_review",
        "type": "charge",
        "customer": customer,
        "amount": amount,
        "message": f"Charge prepared for manual approval for {customer}.",
    }


def compute_execution_tier(
    action: str,
    amount: float,
    confidence: float,
    quality: float,
    risk_level: str,
    abuse_score: int,
    refund_count: int,
    operator_mode: str,
    requires_approval: bool,
) -> str:
    """
    Classify execution safety tier. Read-only — does not change approval behavior.
    """
    act = str(action or "none").strip().lower()
    risk = str(risk_level or "medium").strip().lower()
    mode = str(operator_mode or "balanced").strip().lower()

    if abuse_score >= 3:
        return "assist_only"
    if refund_count >= 5:
        return "assist_only"
    if mode == "conservative":
        return "assist_only"
    if risk == "high":
        return "assist_only"

    if requires_approval:
        return "approval_required"
    if act in {"refund", "charge"} and float(amount or 0) > 0:
        return "approval_required"
    if float(confidence or 0) < 0.78:
        return "approval_required"
    if float(quality or 0) < 0.72:
        return "approval_required"
    if abuse_score >= 2:
        return "approval_required"

    if (
        act in {"none", "credit"}
        and float(confidence or 0) >= 0.88
        and float(quality or 0) >= 0.85
        and risk == "low"
        and int(abuse_score or 0) == 0
        and mode in {"balanced", "delight"}
    ):
        return "safe_autopilot_ready"

    return "approval_required"
