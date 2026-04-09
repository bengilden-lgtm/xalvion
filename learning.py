from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List

from brain import (
    add_rule,
    get_top_rule_objects,
    load_brain,
    register_rule_outcome,
    register_rule_outcome_v2,
    save_brain,
    set_rule_suppression,
)

logger = logging.getLogger("xalvion")

try:
    from outcome_store import get_outcome
except Exception as _get_outcome_imp_err:
    logger.warning("outcome_store.get_outcome unavailable", exc_info=True)

    def get_outcome(outcome_key):
        raise RuntimeError("outcome_store module unavailable") from _get_outcome_imp_err

RULES_FILE = "learned_rules.json"
PATTERN_STORE_KEY = "decision_patterns_v1"

# Pattern expectation constants (deterministic)
_PATTERN_MAX_RECENT_SAMPLES = 30
_PATTERN_RECENCY_HALFLIFE_SEC = 14.0 * 86400.0


def load_rules() -> List[Dict[str, Any]]:
    if not os.path.exists(RULES_FILE):
        return []
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        logger.warning("load_rules_failed rules_file=%s", RULES_FILE, exc_info=True)
        return []


def save_rules(rules: List[Dict[str, Any]]) -> None:
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


def validate_rule(rule: Dict[str, Any]) -> bool:
    if not isinstance(rule, dict):
        return False
    act = rule.get("action")
    if not isinstance(act, dict):
        return False
    try:
        amount = int(act.get("amount", 0) or 0)
    except (TypeError, ValueError):
        return False
    if amount > 50:
        return False
    condition = rule.get("condition")
    if condition is None or not isinstance(condition, dict):
        return False
    if act.get("type") == "refund":
        return False
    return True


def simulate_rule(rule: Dict[str, Any]) -> bool:
    test_cases = [{"ltv": 100, "sentiment": 8}, {"ltv": 900, "sentiment": 2}, {"ltv": 300, "sentiment": 5}]
    for test in test_cases:
        cond = rule.get("condition", {})
        if "sentiment" in cond:
            if test["sentiment"] > 5 and int(rule["action"].get("amount", 0) or 0) > 20:
                return False
    return True


def _candidate_rule(ticket: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any] | None:
    sentiment = int(ticket.get("sentiment", 5) or 5)
    ltv = int(ticket.get("ltv", 0) or 0)
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    if sentiment <= 3 and decision.get("action") == "none":
        return {"trigger": "low_sentiment_no_action", "condition": {"sentiment": "<=3", "issue_type": issue_type}, "action": {"type": "credit", "amount": 15}, "weight": 1.0, "last_used": time.time()}
    if ltv > 800 and decision.get("action") == "none":
        return {"trigger": "high_ltv_protection", "condition": {"ltv": ">800", "issue_type": issue_type}, "action": {"type": "credit", "amount": 30}, "weight": 1.0, "last_used": time.time()}
    return None


def _is_closed_outcome(outcome: Dict[str, Any]) -> bool:
    value = str(outcome.get("crm_status") or outcome.get("status") or outcome.get("ticket_status") or "").strip().lower()
    return value == "closed"


def _safe_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _learning_signal(
    *,
    ticket: Dict[str, Any],
    decision: Dict[str, Any],
    executed: Dict[str, Any],
    outcome_key: str | None,
) -> Dict[str, Any]:
    """
    Deterministic learning signal built from:
    - executed: self-reported execution/tool status (weak evidence)
    - outcome_store row: verified business outcome (strong evidence)

    This keeps channels separate for auditability and avoids unsafe auto-learning
    when only self-report exists.
    """
    t = ticket or {}
    d = decision or {}
    ex = executed or {}

    decision_action = str(d.get("action", ex.get("action", "none")) or "none").strip().lower()
    tool_status = str(ex.get("tool_status", ex.get("status", "")) or "").strip().lower()

    # Operator approval / overrides: best-effort, conservative.
    requires_approval = _safe_bool(d.get("requires_approval", False))
    held = tool_status in {"pending_approval", "manual_review", "approved_pending_execution"}
    operator_approved_exec = bool(requires_approval and (not held) and tool_status not in {"", "no_action"})
    operator_override = _safe_bool(d.get("operator_override", False)) or _safe_bool(d.get("override", False))

    real = None
    if outcome_key:
        try:
            real = get_outcome(outcome_key)
        except Exception:
            real = None

    impact = None
    norm = None
    if real is not None:
        try:
            from outcome_store import compute_outcome_impact, normalize_business_outcome

            impact = compute_outcome_impact(real)
            norm = normalize_business_outcome(real)
        except Exception:
            impact = None
            norm = None

    reopened = bool((real or {}).get("ticket_reopened")) if real is not None else _safe_bool(ex.get("ticket_reopened", False))
    reversed_flag = bool((real or {}).get("refund_reversed")) if real is not None else _safe_bool(ex.get("refund_reversed", False))
    dispute = bool((real or {}).get("dispute_filed")) if real is not None else _safe_bool(ex.get("dispute_filed", False))
    closed = bool((real or {}).get("crm_closed")) if real is not None else _is_closed_outcome(ex)

    impact_score = None
    if isinstance(impact, dict):
        impact_score = impact.get("impact_score")
    if impact_score is not None:
        try:
            impact_score = float(impact_score)
        except Exception:
            impact_score = None

    channel = "real" if real is not None else "self_report"
    operator_approved_outcome = bool((real or {}).get("approved_by_human")) if real is not None else False
    operator_approved_weak = bool(operator_approved_outcome and (impact_score is not None) and (impact_score < 0.58))

    return {
        "channel": channel,
        "decision_action": decision_action,
        "tool_status": tool_status,
        "requires_approval": requires_approval,
        "operator_approved_exec": operator_approved_exec,
        "operator_override": operator_override,
        "real_outcome": real,
        "impact": impact,
        "impact_score": impact_score,
        "business_norm": norm,
        "closed": bool(closed),
        "reopened": bool(reopened),
        "reversed": bool(reversed_flag),
        "dispute": bool(dispute),
        "operator_approved_outcome": operator_approved_outcome,
        "operator_approved_weak": operator_approved_weak,
        "issue_type": str(t.get("issue_type", "general_support") or "general_support"),
        "risk_level": str((t.get("triage") or {}).get("risk_level", d.get("risk_level", "medium")) or "medium").strip().lower(),
    }


def _score_outcome(
    outcome: Dict[str, Any],
    outcome_key: str | None = None,
    *,
    decision: Dict[str, Any] | None = None,
) -> float:
    """
    Score an outcome. If a real outcome exists in outcome_store, use it (outcome-aware).
    Falls back to the self-reported outcome dict for backwards compatibility.

    Refund outcomes are capped so learning does not self-reinforce aggressive refunding.
    """
    real: Dict[str, Any] | None = None
    if outcome_key:
        real = get_outcome(outcome_key)

    dec = decision or {}
    decision_action = str(dec.get("action", outcome.get("action", "none")) or "none").lower()
    decision_risk = str(dec.get("risk_level", "medium") or "medium").lower()

    score = 0.0

    if real is not None:
        try:
            from outcome_store import compute_outcome_impact

            impact = compute_outcome_impact(real)
            base = float(impact["impact_score"]) * 5.0
            if real.get("ticket_reopened"):
                base -= 1.35
            if real.get("refund_reversed"):
                base -= 2.25
            if real.get("dispute_filed"):
                base -= 1.65
            if (
                real.get("success")
                and real.get("auto_resolved")
                and not real.get("refund_reversed")
                and not real.get("dispute_filed")
                and not real.get("ticket_reopened")
                and decision_risk == "low"
                and decision_action in {"none", "credit"}
            ):
                base += 0.55
            if decision_action == "refund":
                base = min(base, 3.85)
            return round(max(0.0, base), 4)
        except Exception as _impact_err:
            logger.warning(
                "outcome_store.compute_outcome_impact failed; using heuristic score path",
                exc_info=True,
            )
        if real.get("success"):
            score += 2.5
        if real.get("auto_resolved"):
            score += 1.0
        if real.get("approved_by_human"):
            score += 0.5
        if real.get("refund_reversed"):
            score -= 3.0
        if real.get("dispute_filed"):
            score -= 2.0
        if real.get("ticket_reopened"):
            score -= 1.5
        if real.get("crm_closed"):
            score += 0.8
        if decision_action == "refund":
            score = min(score, 3.5)
    else:
        # Self-reported fallback — original logic preserved, plus light use of new impact fields
        if _is_closed_outcome(outcome):
            score += 2.0
        if bool(outcome.get("auto_resolved", False)):
            score += 1.0
        score += min(2.0, float(outcome.get("money_saved", 0.0) or 0.0) / 50.0)
        score += min(1.0, float(outcome.get("agent_minutes_saved", 0) or 0) / 10.0)
        score += min(0.85, float(outcome.get("time_saved", 0.0) or 0.0) / 18.0)
        score += min(1.1, float(outcome.get("revenue_saved", 0.0) or 0.0) / 120.0)
        if decision_risk == "low" and decision_action in {"none", "credit"} and bool(outcome.get("auto_resolved")):
            score += 0.35
        if decision_action == "refund":
            score = min(score, 3.4)

    return round(max(0.0, score), 4)


def _pattern_key(ticket: Dict[str, Any], decision: Dict[str, Any]) -> str:
    triage = ticket.get("triage") or {}
    issue = str(ticket.get("issue_type", "general") or "general")[:20]
    action = str(decision.get("action", "none") or "none")[:10]
    risk = str(triage.get("risk_level", "medium") or "medium")[:8]
    tier = str(ticket.get("plan_tier", "free") or "free")[:8]
    return f"{issue}:{action}:{risk}:{tier}"


def _load_patterns() -> dict:
    try:
        from state_store import load_state

        return load_state(PATTERN_STORE_KEY, {})
    except Exception as _load_err:
        logger.error("state_store.load_state failed for decision patterns", exc_info=True)
        raise RuntimeError("state_store.load_state unavailable") from _load_err


def _save_patterns(patterns: dict) -> None:
    try:
        from state_store import save_state

        if len(patterns) > 200:
            sorted_keys = sorted(
                patterns.keys(),
                key=lambda k: float(patterns[k].get("last_updated", 0) or 0),
            )
            for old_key in sorted_keys[: len(patterns) - 200]:
                del patterns[old_key]
        save_state(PATTERN_STORE_KEY, patterns)
    except Exception as _save_err:
        logger.error("state_store.save_state failed for decision patterns", exc_info=True)
        raise RuntimeError("state_store.save_state unavailable") from _save_err


def record_pattern_outcome(
    ticket: Dict[str, Any],
    decision: Dict[str, Any],
    impact_score: float,
) -> None:
    key = _pattern_key(ticket, decision)
    patterns = _load_patterns()

    if key not in patterns:
        patterns[key] = {
            "ema_score":    float(impact_score),
            "sample_count": 1,
            "last_updated": time.time(),
            "recent": [],
        }
    else:
        alpha = 0.25
        prev = float(patterns[key].get("ema_score", 0.5))
        patterns[key]["ema_score"] = round(alpha * float(impact_score) + (1 - alpha) * prev, 4)
        patterns[key]["sample_count"] = int(patterns[key].get("sample_count", 0)) + 1
        patterns[key]["last_updated"] = time.time()

    # bounded recent samples for recency weighting (no PII)
    try:
        recent = patterns[key].get("recent")
        if not isinstance(recent, list):
            recent = []
        recent.append({"ts": time.time(), "impact": float(impact_score)})
        patterns[key]["recent"] = recent[-_PATTERN_MAX_RECENT_SAMPLES:]
    except Exception:
        pass

    _save_patterns(patterns)


def get_pattern_expectation(
    ticket: Dict[str, Any], decision: Dict[str, Any]
) -> dict | None:
    key = _pattern_key(ticket, decision)
    patterns = _load_patterns()
    entry = patterns.get(key)
    if not entry:
        return None

    triage = ticket.get("triage") or {}
    risk_level = str(triage.get("risk_level", "medium") or "medium").strip().lower()
    action = str(decision.get("action", "none") or "none").strip().lower()

    # Sample thresholds (risk-aware)
    min_n = 3
    if action in {"refund", "charge"}:
        min_n = 8
    elif action == "credit":
        min_n = 5
    if risk_level == "high":
        min_n += 2
    elif risk_level == "medium":
        min_n += 1

    sample_count = int(entry.get("sample_count", 0) or 0)
    if sample_count < min_n:
        return None

    ema = float(entry.get("ema_score", 0.5))
    recent = entry.get("recent")
    now = time.time()
    rec_score = None
    rec_n = 0
    if isinstance(recent, list) and recent:
        num = 0.0
        den = 0.0
        for r in recent[-_PATTERN_MAX_RECENT_SAMPLES:]:
            if not isinstance(r, dict):
                continue
            ts = _safe_float(r.get("ts", now), now)
            imp = r.get("impact")
            if imp is None:
                continue
            imp_f = _safe_float(imp, None)  # type: ignore[arg-type]
            if imp_f is None:
                continue
            age = max(0.0, now - ts)
            w = 0.5 ** (age / max(1.0, _PATTERN_RECENCY_HALFLIFE_SEC))
            num += w * float(imp_f)
            den += w
            rec_n += 1
        if den > 0:
            rec_score = round(num / den, 4)

    score = float(rec_score) if rec_score is not None else float(ema)

    # Stability penalties from real outcome aggregates (if available)
    try:
        from outcome_store import get_decision_outcome_stats

        stats = get_decision_outcome_stats(
            str(ticket.get("issue_type", "general_support") or "general_support"),
            action,
            limit=300,
        )
        n_sim = int(stats.get("similar_case_count", 0) or 0)
        rr = stats.get("historical_reopen_rate")
        rev_r = stats.get("reverse_rate")
        disp_r = stats.get("dispute_rate")
        if n_sim >= 8:
            if rr is not None:
                score -= float(rr) * 0.10
            if rev_r is not None:
                score -= float(rev_r) * 0.16
            if disp_r is not None:
                score -= float(disp_r) * 0.14
    except Exception:
        pass

    score = max(0.0, min(1.0, float(score)))
    return {
        "pattern_key":  key,
        "ema_score":    round(float(ema), 4),
        "recency_score": round(float(rec_score), 4) if rec_score is not None else None,
        "score": round(float(score), 4),
        "sample_count": sample_count,
        "min_samples_required": min_n,
        "recent_samples_used": rec_n if rec_score is not None else 0,
        "expectation":  (
            "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"
        ),
    }


def learn_from_ticket(ticket: Dict[str, Any], decision: Dict[str, Any], outcome: Dict[str, Any], outcome_key: str | None = None) -> None:
    rules = load_rules()
    candidate = _candidate_rule(ticket, decision)
    if not candidate:
        return
    if not validate_rule(candidate) or not simulate_rule(candidate):
        return
    sig = _learning_signal(ticket=ticket, decision=decision, executed=outcome, outcome_key=outcome_key)
    impact_score = sig.get("impact_score")

    base_score = _score_outcome(outcome, outcome_key=outcome_key, decision=decision)
    if sig["channel"] == "real" and impact_score is not None:
        conv = 0.85 + float(impact_score) * 2.35
        if sig.get("reopened"):
            conv -= 0.55
        if sig.get("reversed"):
            conv -= 1.25
        if sig.get("dispute"):
            conv -= 1.05
        if sig.get("operator_approved_weak"):
            conv -= 0.35
        try:
            if (sig.get("business_norm") or {}).get("stability") == "stable_auto":
                conv += 0.25
        except Exception:
            pass
        conversion_weight = float(conv)
    else:
        conversion_weight = 0.90 + min(2.0, float(base_score))

    conversion_weight = round(min(3.2, max(0.25, conversion_weight)), 4)
    for rule in rules:
        if rule["trigger"] == candidate["trigger"]:
            rule["weight"] = round(float(rule.get("weight", 1.0)) + (0.5 * conversion_weight), 4)
            rule["last_used"] = time.time()
            save_rules(rules)
            brain = load_brain()
            add_rule(brain, candidate)
            try:
                from outcome_store import public_outcome_digest_for_audit
            except Exception:
                public_outcome_digest_for_audit = lambda _d: {"known": False, "summary": None, "tier": None, "success": None}  # type: ignore[assignment]

            evidence = {
                "outcome_key": outcome_key,
                "outcome_digest": public_outcome_digest_for_audit(sig.get("real_outcome")),
            }
            register_rule_outcome_v2(
                brain,
                candidate["trigger"],
                channel=str(sig.get("channel", "self_report")),
                impact_score=sig.get("impact_score"),
                closed=bool(sig.get("closed")),
                reopened=bool(sig.get("reopened")),
                reversed_flag=bool(sig.get("reversed")),
                dispute=bool(sig.get("dispute")),
                operator_approved=bool(sig.get("operator_approved_outcome") or sig.get("operator_approved_exec")),
                operator_override=bool(sig.get("operator_override")),
                decision_action=str(sig.get("decision_action", "none")),
                evidence=evidence,
            )
            try:
                from outcome_store import compute_outcome_impact

                rowd: Dict[str, Any] = dict(outcome or {})
                if outcome_key:
                    real_o = get_outcome(outcome_key)
                    if real_o:
                        rowd = {**rowd, **real_o}
                _impact = compute_outcome_impact(rowd)
                record_pattern_outcome(ticket, decision, float(_impact["impact_score"]))
            except Exception as _pat_err:
                logger.warning(
                    "record_pattern_outcome skipped (compute_outcome_impact or get_outcome failed)",
                    exc_info=True,
                )

            # Explicit suppression for risky refund-friendly rules (credit in refund/billing contexts).
            try:
                issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
                act = str((candidate.get("action") or {}).get("type", "none") or "none").lower()
                amt = int((candidate.get("action") or {}).get("amount", 0) or 0)
                risky_issue = issue_type in {"refund_request", "billing_duplicate_charge", "billing_issue", "payment_issue"}
                if act == "credit" and risky_issue and amt >= 15:
                    if bool(sig.get("reopened")) or bool(sig.get("reversed")) or bool(sig.get("dispute")):
                        set_rule_suppression(
                            brain,
                            candidate["trigger"],
                            suppressed=True,
                            reason="Suppressed: refund-friendly credit pattern correlated with unstable outcome (reopen/reversal/dispute).",
                            until_ts=time.time() + 21.0 * 86400.0,
                            evidence=evidence,
                        )
            except Exception:
                pass
            return
    candidate["weight"] = round(max(0.05, conversion_weight), 4)
    rules.append(candidate)
    save_rules(rules)
    brain = load_brain()
    add_rule(brain, candidate)
    try:
        from outcome_store import public_outcome_digest_for_audit
    except Exception:
        public_outcome_digest_for_audit = lambda _d: {"known": False, "summary": None, "tier": None, "success": None}  # type: ignore[assignment]
    evidence_new = {
        "outcome_key": outcome_key,
        "outcome_digest": public_outcome_digest_for_audit(sig.get("real_outcome")),
    }
    register_rule_outcome_v2(
        brain,
        candidate["trigger"],
        channel=str(sig.get("channel", "self_report")),
        impact_score=sig.get("impact_score"),
        closed=bool(sig.get("closed")),
        reopened=bool(sig.get("reopened")),
        reversed_flag=bool(sig.get("reversed")),
        dispute=bool(sig.get("dispute")),
        operator_approved=bool(sig.get("operator_approved_outcome") or sig.get("operator_approved_exec")),
        operator_override=bool(sig.get("operator_override")),
        decision_action=str(sig.get("decision_action", "none")),
        evidence=evidence_new,
    )
    try:
        from outcome_store import compute_outcome_impact

        rowd_new: Dict[str, Any] = dict(outcome or {})
        if outcome_key:
            real_on = get_outcome(outcome_key)
            if real_on:
                rowd_new = {**rowd_new, **real_on}
        _impact_n = compute_outcome_impact(rowd_new)
        record_pattern_outcome(ticket, decision, float(_impact_n["impact_score"]))
    except Exception as _pat_err:
        logger.warning(
            "record_pattern_outcome skipped (compute_outcome_impact or get_outcome failed)",
            exc_info=True,
        )

    try:
        issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
        act = str((candidate.get("action") or {}).get("type", "none") or "none").lower()
        amt = int((candidate.get("action") or {}).get("amount", 0) or 0)
        risky_issue = issue_type in {"refund_request", "billing_duplicate_charge", "billing_issue", "payment_issue"}
        if act == "credit" and risky_issue and amt >= 15:
            if bool(sig.get("reopened")) or bool(sig.get("reversed")) or bool(sig.get("dispute")):
                set_rule_suppression(
                    brain,
                    candidate["trigger"],
                    suppressed=True,
                    reason="Suppressed: refund-friendly credit pattern correlated with unstable outcome (reopen/reversal/dispute).",
                    until_ts=time.time() + 21.0 * 86400.0,
                    evidence=evidence_new,
                )
    except Exception:
        pass


def apply_learned_rules(ticket: Dict[str, Any], top_rules: List[Dict[str, Any]] | None = None) -> Dict[str, Any] | None:
    if top_rules is not None:
        rules = top_rules
    else:
        try:
            from brain import get_top_rule_objects as _get_top_rule_objects
            from brain import load_brain as _load_brain

            _brain = _load_brain()
            rules = _get_top_rule_objects(_brain, 10)
            if not rules:
                rules = load_rules()
        except Exception as _brain_rules_err:
            logger.warning(
                "brain rule objects unavailable; falling back to learned_rules.json",
                exc_info=True,
            )
            rules = load_rules()
    if not rules:
        return None
    rules = sorted(rules, key=lambda x: float(x.get("weight", 0)), reverse=True)
    for rule in rules:
        cond = rule.get("condition", {})
        if "sentiment" in cond and int(ticket.get("sentiment", 10) or 10) <= 3:
            rule["last_used"] = time.time()
            if not top_rules:
                save_rules(rules)
            return rule["action"]
        if "ltv" in cond and int(ticket.get("ltv", 0) or 0) > 800:
            rule["last_used"] = time.time()
            if not top_rules:
                save_rules(rules)
            return rule["action"]
    return None


def update_rule_feedback(ticket: Dict[str, Any], decision: Dict[str, Any], outcome: Dict[str, Any]) -> None:
    rules = load_rules()
    decision_action = str(decision.get("action", "none") or "none")
    sig = _learning_signal(ticket=ticket, decision=decision, executed=outcome, outcome_key=None)
    impact_score = sig.get("impact_score")
    if impact_score is not None:
        success = float(impact_score) >= 0.58 and not (sig.get("reopened") or sig.get("reversed") or sig.get("dispute"))
    else:
        success = _score_outcome(outcome, decision=decision) > 0.9
    for rule in rules:
        trigger = rule.get("trigger", "")
        matches_low_sentiment = trigger == "low_sentiment_no_action" and int(ticket.get("sentiment", 10) or 10) <= 3
        matches_high_ltv = trigger == "high_ltv_protection" and int(ticket.get("ltv", 0) or 0) > 800
        if matches_low_sentiment or matches_high_ltv:
            delta = 0.40 if success else -0.65
            if decision_action == "credit" and _is_closed_outcome(outcome):
                delta += 0.55
            rule["weight"] = round(max(0.0, float(rule.get("weight", 1.0)) + delta), 4)
            rule["last_used"] = time.time()
            brain = load_brain()
            try:
                register_rule_outcome_v2(
                    brain,
                    trigger,
                    channel=str(sig.get("channel", "self_report")),
                    impact_score=sig.get("impact_score"),
                    closed=bool(sig.get("closed") or _is_closed_outcome(outcome)),
                    reopened=bool(sig.get("reopened")),
                    reversed_flag=bool(sig.get("reversed")),
                    dispute=bool(sig.get("dispute")),
                    operator_approved=bool(sig.get("operator_approved_outcome") or sig.get("operator_approved_exec")),
                    operator_override=bool(sig.get("operator_override")),
                    decision_action=str(sig.get("decision_action", decision_action)),
                    evidence={"note": "update_rule_feedback"},
                )
            except Exception:
                register_rule_outcome(brain, trigger, closed=_is_closed_outcome(outcome), positive=success)
            save_brain(brain)
    save_rules(rules)


def sync_rules_to_brain() -> None:
    """
    Startup sync: push rules from learned_rules.json into brain
    state if brain is missing them. add_rule() is idempotent for
    existing triggers — safe to call multiple times.
    Does not modify the JSON file.
    """
    rules = load_rules()
    if not rules:
        return
    try:
        from brain import add_rule as _add_rule
        from brain import load_brain as _load_brain

        brain = _load_brain()
        existing_triggers = {
            r.get("trigger", "")
            for r in brain.get("learned_rules", [])
        }
        for rule in rules:
            trigger = rule.get("trigger", "")
            if trigger and trigger not in existing_triggers:
                _add_rule(brain, rule)
    except Exception as _sync_err:
        logger.error("sync_rules_to_brain failed", exc_info=True)
        raise RuntimeError("sync_rules_to_brain failed") from _sync_err


def decay_rules() -> None:
    rules = load_rules()
    now = time.time()
    updated: List[Dict[str, Any]] = []
    for rule in rules:
        age = now - float(rule.get("last_used", now))
        if age > 86400:
            rule["weight"] = round(float(rule.get("weight", 1.0)) - 0.18, 4)
        if float(rule.get("weight", 0)) > 0:
            updated.append(rule)
    save_rules(updated)
