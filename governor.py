"""
governor.py
Final authority governance layer between decisioning and execution.

Hard constraints:
- Pure + deterministic (no IO, no external calls).
- No DB writes.
- Dict-in / dict-out API.
- Conservative defaults: on ambiguity, force review (never crash).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_plan_tier(plan_tier: str) -> str:
    """
    Normalize plan tier into {free, pro, elite, dev}. Unknown -> free.
    """
    t = str(plan_tier or "").strip().lower()
    if t in {"free", "pro", "elite", "dev"}:
        return t
    # allow common aliases without breaking callers
    if t in {"developer", "internal"}:
        return "dev"
    if t in {"enterprise", "ent"}:
        return "elite"
    return "free"


def plan_limits(plan_tier: str) -> dict:
    """
    Deterministic plan policy limits for financial motions and monthly ticket caps.

    ``monthly_tickets`` is the canonical per-tier operator/ticket monthly allowance
    (aligned with product tiers; enforcement reads this field).
    """
    tier = normalize_plan_tier(plan_tier)
    if tier == "pro":
        return {
            "max_refund": 50,
            "max_credit": 30,
            "can_auto_refund": True,
            "can_auto_credit": True,
            "requires_human_for_charge": True,
            "monthly_tickets": 500,
        }
    if tier == "elite":
        return {
            "max_refund": 100,
            "max_credit": 50,
            "can_auto_refund": True,
            "can_auto_credit": True,
            "requires_human_for_charge": True,
            "monthly_tickets": 5000,
        }
    if tier == "dev":
        # High-but-safe defaults. Charges remain human-reviewed.
        return {
            "max_refund": 10_000,
            "max_credit": 10_000,
            "can_auto_refund": True,
            "can_auto_credit": True,
            "requires_human_for_charge": True,
            "monthly_tickets": 10**9,
        }
    # free (default)
    return {
        "max_refund": 15,
        "max_credit": 10,
        "can_auto_refund": False,
        "can_auto_credit": True,
        "requires_human_for_charge": True,
        "monthly_tickets": 12,
    }


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        # allow numeric strings, floats
        n = int(float(v))
        return n
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _to_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _risk_level_from_score(score: int) -> str:
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def compute_governor_risk(ticket: dict, decision: dict, memory: dict | None = None) -> dict:
    """
    Compute a conservative risk score (0-5) and explain factors.
    """
    t = ticket or {}
    d = decision or {}
    m = memory or {}

    factors: List[str] = []
    score = 0

    action = str(d.get("action", "none") or "none").strip().lower()
    amount = _to_float(d.get("amount", 0), 0.0)

    triage = t.get("triage") if isinstance(t.get("triage"), dict) else {}
    issue_type = str(t.get("issue_type") or t.get("type") or "general_support").strip().lower()
    sentiment = _to_int(t.get("sentiment", m.get("sentiment_avg", 5)), 5)

    abuse_score = _to_int(m.get("abuse_score", t.get("abuse_score", 0)), 0)
    refund_count = _to_int(m.get("refund_count", 0), 0)
    complaint_count = _to_int(m.get("complaint_count", 0), 0)
    review_count = _to_int(m.get("review_count", 0), 0)
    repeat_customer = _to_bool(m.get("repeat_customer", t.get("repeat_customer", False)), False)

    plan_tier = normalize_plan_tier(str(t.get("plan_tier", m.get("plan_tier", "free")) or "free"))
    limits = plan_limits(plan_tier)

    financial = action in {"refund", "credit", "charge"}
    if action == "charge":
        score += 3
        factors.append("Charge action requested (always high-risk and human-reviewed)")
    elif action == "refund":
        score += 2
        factors.append("Refund action requested")
    elif action == "credit":
        score += 1
        factors.append("Credit action requested")

    if financial and amount > 0:
        if amount >= max(float(limits.get("max_refund", 0) or 0), float(limits.get("max_credit", 0) or 0)) * 0.8:
            score += 1
            factors.append(f"High amount for tier ({plan_tier}): {amount:.2f}")
        if amount >= 100:
            score += 1
            factors.append("Large financial amount (>= 100)")

    # Sentiment: treat 1-3 as low, 4-6 medium, 7-10 high
    if sentiment <= 3:
        score += 1
        factors.append("Low customer sentiment")

    # Issue types that tend to be policy-sensitive
    if "billing" in issue_type or issue_type in {"payment_issue", "refund_request", "billing_duplicate_charge"}:
        if financial:
            score += 1
            factors.append("Billing-related financial motion")

    # Abuse signals dominate
    if abuse_score >= 3:
        score += 3
        factors.append("Severe abuse indicators (abuse_score >= 3)")
    elif abuse_score >= 2:
        score += 2
        factors.append("Abuse indicators present (abuse_score >= 2)")
    elif abuse_score == 1:
        score += 1
        factors.append("Mild abuse indicators (abuse_score = 1)")

    if refund_count >= 3:
        score += 2
        factors.append(f"Repeated refunds in memory (refund_count={refund_count})")
    elif refund_count >= 1 and action == "refund":
        score += 1
        factors.append(f"Prior refunds exist (refund_count={refund_count})")

    if complaint_count >= 2:
        score += 1
        factors.append(f"Multiple complaints in memory (complaint_count={complaint_count})")

    if review_count >= 2:
        score += 1
        factors.append(f"Previously held for review (review_count={review_count})")

    # Small reduction: repeat customer + small credit only, never reduces below abuse concerns
    if repeat_customer and action == "credit" and 0 < amount <= 10 and abuse_score == 0:
        score -= 1
        factors.append("Repeat customer with small credit (risk reduced slightly)")

    # Outcome intelligence on the decision payload — tighten only (never relax abuse/plan gates)
    sim_n = _to_int(d.get("similar_case_count", 0), 0)
    band = str(d.get("outcome_confidence_band") or "").strip().lower()
    if band == "low" and sim_n >= 5:
        score += 1
        factors.append("Outcome history confidence band is low for this issue/action pattern")
    try:
        h_rr = d.get("historical_reopen_rate")
        if sim_n >= 8 and h_rr is not None and float(h_rr) >= 0.22:
            score += 1
            factors.append("Elevated historical reopen rate for this action pattern")
    except Exception:
        pass
    try:
        h_sr = d.get("historical_success_rate")
        if sim_n >= 8 and h_sr is not None and float(h_sr) <= 0.52:
            score += 1
            factors.append("Low historical success rate for this action pattern")
    except Exception:
        pass
    br = d.get("decision_confidence_breakdown")
    if isinstance(br, dict):
        try:
            oc = br.get("overall_confidence")
            if oc is not None and float(oc) < 0.58 and sim_n >= 6:
                score += 1
                factors.append("Structural decision confidence is low relative to outcome history")
        except Exception:
            pass

    # Clamp score into 0-5
    if score < 0:
        score = 0
    if score > 5:
        score = 5

    level = _risk_level_from_score(score)
    return {"score": int(score), "level": level, "factors": factors}


def validate_decision(ticket: dict, decision: dict, memory: dict | None = None) -> dict:
    """
    Validate if a decision is eligible for auto-execution under policy.
    Conservative: missing context -> force review, not crash.
    """
    t = ticket or {}
    d = decision or {}
    m = memory or {}

    violations: List[str] = []

    action = str(d.get("action", "none") or "none").strip().lower()
    amount = _to_float(d.get("amount", 0), 0.0)
    plan_tier = normalize_plan_tier(str(t.get("plan_tier", m.get("plan_tier", "free")) or "free"))
    limits = plan_limits(plan_tier)

    abuse_score = _to_int(m.get("abuse_score", t.get("abuse_score", 0)), 0)
    refund_count = _to_int(m.get("refund_count", 0), 0)
    issue_type = str(t.get("issue_type") or t.get("type") or "general_support").strip().lower()
    sentiment = _to_int(t.get("sentiment", m.get("sentiment_avg", 5)), 5)

    financial = action in {"refund", "credit", "charge"}

    # Missing critical context for financial motions should not auto-execute
    if financial:
        # customer identifier is required to safely execute financial tools in most integrations
        customer = t.get("customer") or t.get("customer_id") or t.get("customer_email")
        if not customer:
            violations.append("Missing customer identity for financial action")
        if amount <= 0:
            violations.append("Missing or non-positive amount for financial action")

    # Charge: always needs a human
    if action == "charge":
        violations.append("Charge requires human review")

    # Tier policy: free (and tiers without auto-refund) never auto-execute refunds
    if action == "refund" and not bool(limits.get("can_auto_refund")):
        violations.append(f"Plan tier {plan_tier} does not allow automatic refunds")

    # Plan caps
    if action == "refund" and amount > float(limits.get("max_refund", 0) or 0):
        violations.append(f"Refund exceeds plan limit for {plan_tier} (max_refund={limits.get('max_refund')})")
    if action == "credit" and amount > float(limits.get("max_credit", 0) or 0):
        violations.append(f"Credit exceeds plan limit for {plan_tier} (max_credit={limits.get('max_credit')})")

    # Abuse blocks auto financial execution
    if abuse_score >= 2 and financial:
        violations.append("Abuse score blocks auto financial execution (abuse_score >= 2)")

    # Repeated refunds should force review for refunds
    if refund_count >= 3 and action == "refund":
        violations.append("Repeated refunds require review (refund_count >= 3)")

    # High-risk billing issues force review
    if financial and ("billing" in issue_type or issue_type in {"payment_issue", "refund_request", "billing_duplicate_charge"}):
        if sentiment <= 3:
            violations.append("Billing + low sentiment requires review")

    approved = len(violations) == 0
    reason: Optional[str] = None if approved else "Governor policy requires review"
    return {"approved": bool(approved), "reason": reason, "violations": violations}


def gate_execution(ticket: dict, decision: dict, memory: dict | None = None) -> dict:
    """
    Combine validation + risk into an execution gate.
    Returns execution_mode: auto | review | blocked
    """
    t = ticket or {}
    d = decision or {}
    m = memory or {}

    action = str(d.get("action", "none") or "none").strip().lower()
    amount = _to_float(d.get("amount", 0), 0.0)
    financial = action in {"refund", "credit", "charge"}

    risk = compute_governor_risk(t, d, memory)
    val = validate_decision(t, d, memory)

    approved = bool(val.get("approved", False))
    violations = list(val.get("violations") or [])

    # Default conservative posture
    execution_mode = "review"

    # Charges never auto
    if action == "charge":
        execution_mode = "review"
    elif not financial:
        # Non-financial actions generally can be auto unless high risk signals
        execution_mode = "auto" if risk["level"] == "low" else "review"
    else:
        # financial (refund/credit) – require valid policy + low risk for auto
        if approved and risk["level"] == "low":
            execution_mode = "auto"
        else:
            execution_mode = "review"

    # Block only when truly out of policy or missing critical requirements
    critical_blocks: List[str] = []
    for v in violations:
        if "Missing customer identity" in v:
            critical_blocks.append(v)
        if "non-positive amount" in v and financial and amount <= 0:
            critical_blocks.append(v)

    # Out-of-policy financial amount is not "blocked" by default; it can be reviewed/human-approved.
    # Abuse_score >= 2 blocks auto financial execution but should still be reviewable by a human.
    # So we only block on critical missing requirements.
    if critical_blocks:
        execution_mode = "blocked"
        governor_reason = "Blocked: missing critical context for safe execution"
    elif execution_mode == "auto":
        governor_reason = "Approved for auto execution under governor policy"
    else:
        governor_reason = "Review required under governor policy"

    # Elevated risk: high always reviews; medium reviews unless tier policy allows in-cap auto motion.
    if execution_mode == "auto" and financial:
        plan_tier = normalize_plan_tier(str(t.get("plan_tier", m.get("plan_tier", "free")) or "free"))
        limits = plan_limits(plan_tier)
        refund_auto_eligible = (
            action == "refund"
            and bool(limits.get("can_auto_refund"))
            and amount <= float(limits.get("max_refund", 0) or 0)
            and approved
        )
        credit_auto_eligible = (
            action == "credit"
            and bool(limits.get("can_auto_credit"))
            and amount <= float(limits.get("max_credit", 0) or 0)
            and approved
        )
        if risk["level"] == "high":
            execution_mode = "review"
            governor_reason = "Review required: elevated risk for financial action"
        elif risk["level"] == "medium" and not (refund_auto_eligible or credit_auto_eligible):
            execution_mode = "review"
            governor_reason = "Review required: elevated risk for financial action"

    requires_approval = execution_mode in {"review", "blocked"} or action == "charge"

    return {
        "execution_mode": execution_mode,
        "requires_approval": bool(requires_approval),
        "governor_reason": str(governor_reason),
        "governor_risk_level": str(risk.get("level", "medium")),
        "governor_risk_score": int(risk.get("score", 3)),
        "governor_factors": list(risk.get("factors") or []),
        "approved": bool(approved),
        "violations": violations,
    }


def derive_execution_tier(governor_result: dict, decision: dict) -> str:
    """
    Map governor execution_mode to execution_tier without downgrading safety.
    """
    g = governor_result or {}
    mode = str(g.get("execution_mode", "") or "").strip().lower()
    if mode == "auto":
        return "safe_autopilot_ready"
    if mode == "review":
        return "approval_required"
    # blocked / unknown
    return "assist_only"

