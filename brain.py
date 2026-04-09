from __future__ import annotations

import time
from typing import Any, Dict, List

from state_store import load_state, save_state

BRAIN_STATE_KEY = "brain_v1"


def default_brain() -> Dict[str, Any]:
    return {
        "core_knowledge": [],
        "soul_file": "",
        "learned_rules": [
            {
                "trigger": "low_sentiment_shipping",
                "condition": {"issue_type": "shipping_issue", "sentiment_lte": 3},
                "action": {"type": "credit", "amount": 10},
            }
        ],
        "rule_weights": {},
        "rule_scores": {},
        "rule_outcomes": {},
        # Rich, auditable outcome-driven learning stats (additive; older brains ignore)
        "rule_stats": {},
        # Operator/audit-safe per-rule event log (bounded)
        "rule_audit": {},
        # Explicit suppressions (safety + performance)
        "rule_suppressions": {},
        "system_prompt": "",
        "prompt_history": [],
    }


def save_brain(brain: Dict[str, Any]) -> None:
    save_state(BRAIN_STATE_KEY, brain)


def normalize_rule(rule: Any) -> Dict[str, Any] | None:
    if isinstance(rule, dict):
        trigger = str(rule.get("trigger", "")).strip() or "unknown_rule"
        condition = rule.get("condition", {})
        action = rule.get("action", {"type": "none", "amount": 0})
        if not isinstance(condition, dict):
            condition = {}
        if not isinstance(action, dict):
            action = {"type": "none", "amount": 0}
        return {"trigger": trigger, "condition": condition, "action": {"type": str(action.get("type", "none")), "amount": int(action.get("amount", 0) or 0)}}
    if isinstance(rule, str):
        text = rule.strip()
        if not text:
            return None
        lowered = text.lower()
        if "frustration" in lowered or "empat" in lowered:
            return {"trigger": "frustration_empathy", "condition": {"sentiment_lte": 4}, "action": {"type": "credit", "amount": 10}}
        if "vague" in lowered or "direct" in lowered:
            return {"trigger": "direct_actionable_response", "condition": {"sentiment_lte": 6}, "action": {"type": "none", "amount": 0}}
        if "clarity" in lowered or "confident tone" in lowered:
            return {"trigger": "clarity_confidence_rule", "condition": {}, "action": {"type": "none", "amount": 0}}
        return {"trigger": text[:50].lower().replace(" ", "_"), "condition": {}, "action": {"type": "none", "amount": 0}}
    return None


def normalize_brain(brain: Dict[str, Any]) -> Dict[str, Any]:
    defaults = default_brain()
    for key, value in defaults.items():
        if key not in brain:
            brain[key] = value
    raw_rules = brain.get("learned_rules", [])
    if not isinstance(raw_rules, list):
        raw_rules = []
    normalized_rules: List[Dict[str, Any]] = []
    seen = set()
    for rule in raw_rules:
        normalized = normalize_rule(rule)
        if not normalized:
            continue
        trigger = normalized["trigger"]
        if trigger in seen:
            continue
        seen.add(trigger)
        normalized_rules.append(normalized)
    if not normalized_rules:
        normalized_rules = defaults["learned_rules"]
    brain["learned_rules"] = normalized_rules
    if not isinstance(brain.get("rule_weights"), dict):
        brain["rule_weights"] = {}
    if not isinstance(brain.get("rule_scores"), dict):
        brain["rule_scores"] = {}
    if not isinstance(brain.get("rule_outcomes"), dict):
        brain["rule_outcomes"] = {}
    if not isinstance(brain.get("rule_stats"), dict):
        brain["rule_stats"] = {}
    if not isinstance(brain.get("rule_audit"), dict):
        brain["rule_audit"] = {}
    if not isinstance(brain.get("rule_suppressions"), dict):
        brain["rule_suppressions"] = {}
    if not isinstance(brain.get("prompt_history"), list):
        brain["prompt_history"] = []
    for rule in brain["learned_rules"]:
        trigger = rule["trigger"]
        brain["rule_weights"].setdefault(trigger, 1)
        brain["rule_scores"].setdefault(trigger, 1.0)
        brain["rule_outcomes"].setdefault(trigger, {"wins": 0, "losses": 0, "closed_wins": 0})
        brain["rule_stats"].setdefault(
            trigger,
            {
                "n_total": 0,
                "n_real_outcomes": 0,
                "n_self_report_only": 0,
                "n_operator_approved": 0,
                "n_operator_override": 0,
                "n_success": 0,
                "n_auto_success": 0,
                "n_reopened": 0,
                "n_reversed": 0,
                "n_dispute": 0,
                "n_closed": 0,
                "n_good": 0,
                "n_bad": 0,
                "underperform_streak": 0,
                "last_event_ts": 0.0,
                "last_real_outcome_ts": 0.0,
                "last_impact_score": None,
            },
        )
    return brain


def load_brain() -> Dict[str, Any]:
    brain = load_state(BRAIN_STATE_KEY, default_brain())
    brain = normalize_brain(brain)
    if not brain.get("system_prompt"):
        update_system_prompt(brain)
        save_brain(brain)
    return brain


def compute_rule_score(brain: Dict[str, Any], trigger: str) -> float:
    base = float(brain.get("rule_scores", {}).get(trigger, 1.0))
    weight = float(brain.get("rule_weights", {}).get(trigger, 1.0))
    outcomes = brain.get("rule_outcomes", {}).get(trigger, {})
    wins = float(outcomes.get("wins", 0))
    losses = float(outcomes.get("losses", 0))
    closed_wins = float(outcomes.get("closed_wins", 0))
    conversion_bonus = closed_wins * 0.8
    penalty = losses * 0.35
    # Outcome-driven stability penalty (reopens/reversals/disputes) — deterministic + explainable.
    stats = (brain.get("rule_stats") or {}).get(trigger) or {}
    reopened = float(stats.get("n_reopened", 0) or 0)
    reversed_n = float(stats.get("n_reversed", 0) or 0)
    disputes = float(stats.get("n_dispute", 0) or 0)
    streak = float(stats.get("underperform_streak", 0) or 0)
    stability_pen = reopened * 0.55 + reversed_n * 1.10 + disputes * 0.95 + max(0.0, streak - 2.0) * 0.35

    # Explicit suppression is a strong down-rank without deleting evidence.
    sup = (brain.get("rule_suppressions") or {}).get(trigger) or {}
    suppressed = bool(sup.get("suppressed", False))
    sup_pen = 6.0 if suppressed else 0.0

    return round(base + (weight * 0.12) + (wins * 0.18) + conversion_bonus - penalty - stability_pen - sup_pen, 4)


def get_top_rule_objects(brain: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    scored = []
    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
        # Suppressed rules are not eligible for selection (kept for audit).
        sup = (brain.get("rule_suppressions") or {}).get(trigger) or {}
        if bool(sup.get("suppressed", False)):
            continue
        score = compute_rule_score(brain, trigger)
        scored.append((score, rule))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [rule for _, rule in scored[:limit]]


def add_rule(brain: Dict[str, Any], rule: Dict[str, Any] | str) -> None:
    normalized = normalize_rule(rule)
    if not normalized:
        return
    trigger = normalized["trigger"]
    existing = next((r for r in brain["learned_rules"] if r.get("trigger") == trigger), None)
    if existing is None:
        brain["learned_rules"].append(normalized)
        brain["rule_weights"][trigger] = 1
        brain["rule_scores"][trigger] = 1.0
        brain["rule_outcomes"][trigger] = {"wins": 0, "losses": 0, "closed_wins": 0}
        brain.setdefault("rule_stats", {})[trigger] = {
            "n_total": 0,
            "n_real_outcomes": 0,
            "n_self_report_only": 0,
            "n_operator_approved": 0,
            "n_operator_override": 0,
            "n_success": 0,
            "n_auto_success": 0,
            "n_reopened": 0,
            "n_reversed": 0,
            "n_dispute": 0,
            "n_closed": 0,
            "n_good": 0,
            "n_bad": 0,
            "underperform_streak": 0,
            "last_event_ts": 0.0,
            "last_real_outcome_ts": 0.0,
            "last_impact_score": None,
        }
    else:
        brain["rule_weights"][trigger] = min(
            500,
            int(brain["rule_weights"].get(trigger, 1)) + 1,
        )
        brain["rule_scores"][trigger] = min(
            50.0,
            round(float(brain["rule_scores"].get(trigger, 1.0)) + 0.2, 4),
        )
    update_system_prompt(brain)
    save_brain(brain)


def _append_rule_audit(brain: Dict[str, Any], trigger: str, event: Dict[str, Any]) -> None:
    """
    Append an operator-safe audit event for a trigger.
    Bounded to last 40 entries per rule.
    """
    if not isinstance(event, dict):
        return
    audit = brain.setdefault("rule_audit", {}).setdefault(trigger, [])
    if not isinstance(audit, list):
        audit = []
    audit.append(event)
    audit = audit[-40:]
    brain["rule_audit"][trigger] = audit


def set_rule_suppression(
    brain: Dict[str, Any],
    trigger: str,
    *,
    suppressed: bool,
    reason: str,
    until_ts: float | None = None,
    evidence: Dict[str, Any] | None = None,
) -> None:
    """
    Explicitly suppress (or unsuppress) a learned rule trigger.
    Deterministic, auditable, and does not delete prior learning evidence.
    """
    trig = str(trigger or "").strip() or "unknown_rule"
    now = time.time()
    entry = {
        "suppressed": bool(suppressed),
        "reason": str(reason or "").strip()[:260] or None,
        "set_at": float(now),
        "until_ts": float(until_ts) if until_ts is not None else None,
    }
    brain.setdefault("rule_suppressions", {})[trig] = entry
    _append_rule_audit(
        brain,
        trig,
        {
            "ts": float(now),
            "event": "suppression_set" if suppressed else "suppression_cleared",
            "reason": entry["reason"],
            "until_ts": entry["until_ts"],
            "evidence": dict(evidence or {}) if isinstance(evidence, dict) else None,
        },
    )
    update_system_prompt(brain)
    save_brain(brain)


def register_rule_outcome(brain: Dict[str, Any], trigger: str, *, closed: bool = False, positive: bool = True) -> None:
    outcomes = brain.setdefault("rule_outcomes", {}).setdefault(trigger, {"wins": 0, "losses": 0, "closed_wins": 0})
    if positive:
        outcomes["wins"] = int(outcomes.get("wins", 0)) + 1
        if closed:
            outcomes["closed_wins"] = int(outcomes.get("closed_wins", 0)) + 1
        brain.setdefault("rule_weights", {})[trigger] = int(brain.get("rule_weights", {}).get(trigger, 1)) + 1
    else:
        outcomes["losses"] = int(outcomes.get("losses", 0)) + 1
        brain.setdefault("rule_weights", {})[trigger] = max(1, int(brain.get("rule_weights", {}).get(trigger, 1)) - 1)
    brain.setdefault("rule_scores", {})[trigger] = compute_rule_score(brain, trigger)
    update_system_prompt(brain)
    save_brain(brain)


def register_rule_outcome_v2(
    brain: Dict[str, Any],
    trigger: str,
    *,
    channel: str,
    impact_score: float | None,
    closed: bool,
    reopened: bool,
    reversed_flag: bool,
    dispute: bool,
    operator_approved: bool,
    operator_override: bool,
    decision_action: str,
    evidence: Dict[str, Any] | None = None,
) -> None:
    """
    Outcome-aware reinforcement entry point.
    - channel: "real" | "self_report"
    - impact_score: 0..1 when real outcome known (None allowed)
    Updates rule_stats + classic wins/losses, then recomputes rule score.
    """
    trig = str(trigger or "").strip() or "unknown_rule"
    stats = brain.setdefault("rule_stats", {}).setdefault(trig, {})
    if not isinstance(stats, dict):
        stats = {}
    now = time.time()

    # --- update counts ---
    stats["n_total"] = int(stats.get("n_total", 0) or 0) + 1
    if str(channel or "").strip().lower() == "real":
        stats["n_real_outcomes"] = int(stats.get("n_real_outcomes", 0) or 0) + 1
        stats["last_real_outcome_ts"] = float(now)
    else:
        stats["n_self_report_only"] = int(stats.get("n_self_report_only", 0) or 0) + 1
    if operator_approved:
        stats["n_operator_approved"] = int(stats.get("n_operator_approved", 0) or 0) + 1
    if operator_override:
        stats["n_operator_override"] = int(stats.get("n_operator_override", 0) or 0) + 1
    if closed:
        stats["n_closed"] = int(stats.get("n_closed", 0) or 0) + 1
    if reopened:
        stats["n_reopened"] = int(stats.get("n_reopened", 0) or 0) + 1
    if reversed_flag:
        stats["n_reversed"] = int(stats.get("n_reversed", 0) or 0) + 1
    if dispute:
        stats["n_dispute"] = int(stats.get("n_dispute", 0) or 0) + 1

    # --- interpret impact into good/bad + streak ---
    good = False
    bad = False
    if impact_score is not None:
        try:
            sc = float(impact_score)
        except Exception:
            sc = None
        if sc is not None:
            stats["last_impact_score"] = float(sc)
            # Deterministic bands (aligned with outcome_store impact labels)
            if sc >= 0.58:
                good = True
            elif sc < 0.38:
                bad = True

    # Stability events override "good" — an outcome that reopens/reverses/disputes is treated as underperforming.
    if reopened or reversed_flag or dispute:
        bad = True
        good = False

    if good:
        stats["n_good"] = int(stats.get("n_good", 0) or 0) + 1
        stats["underperform_streak"] = 0
    elif bad:
        stats["n_bad"] = int(stats.get("n_bad", 0) or 0) + 1
        stats["underperform_streak"] = int(stats.get("underperform_streak", 0) or 0) + 1
    else:
        # neutral: drift streak toward 0 slowly
        stats["underperform_streak"] = max(0, int(stats.get("underperform_streak", 0) or 0) - 1)

    stats["last_event_ts"] = float(now)
    brain["rule_stats"][trig] = stats

    # --- classic wins/losses for backward compatibility ---
    positive = bool(good) and not bool(bad)
    register_rule_outcome(brain, trig, closed=bool(closed), positive=positive)

    _append_rule_audit(
        brain,
        trig,
        {
            "ts": float(now),
            "event": "rule_outcome",
            "channel": str(channel or "unknown"),
            "decision_action": str(decision_action or "none"),
            "impact_score": float(impact_score) if impact_score is not None else None,
            "closed": bool(closed),
            "reopened": bool(reopened),
            "reversed": bool(reversed_flag),
            "dispute": bool(dispute),
            "operator_approved": bool(operator_approved),
            "operator_override": bool(operator_override),
            "streak": int(stats.get("underperform_streak", 0) or 0),
            "evidence": dict(evidence or {}) if isinstance(evidence, dict) else None,
        },
    )


def decay_rules(brain: Dict[str, Any]) -> None:
    to_remove = []
    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
        current = float(brain["rule_scores"].get(trigger, 1.0)) * 0.992
        current = min(current, 50.0)
        brain["rule_scores"][trigger] = round(current, 4)
        # Suppression expiry is deterministic based on timestamp; expired suppressions are cleared.
        sup = (brain.get("rule_suppressions") or {}).get(trigger)
        if isinstance(sup, dict) and bool(sup.get("suppressed", False)):
            until_ts = sup.get("until_ts")
            try:
                if until_ts is not None and float(until_ts) > 0 and time.time() >= float(until_ts):
                    sup["suppressed"] = False
                    sup["reason"] = (str(sup.get("reason") or "")[:180] + " (expired)")[:260] if sup.get("reason") else "expired"
                    brain["rule_suppressions"][trigger] = sup
            except Exception:
                pass
        if current < 0.30:
            to_remove.append(trigger)
    if to_remove:
        brain["learned_rules"] = [r for r in brain["learned_rules"] if r.get("trigger") not in to_remove]
        for trigger in to_remove:
            brain["rule_scores"].pop(trigger, None)
            brain["rule_weights"].pop(trigger, None)
            brain["rule_outcomes"].pop(trigger, None)
            brain.get("rule_stats", {}).pop(trigger, None)
            brain.get("rule_audit", {}).pop(trigger, None)
            brain.get("rule_suppressions", {}).pop(trigger, None)
    update_system_prompt(brain)
    save_brain(brain)


def build_system_prompt(brain: Dict[str, Any]) -> str:
    rules_text = []
    for rule in get_top_rule_objects(brain, 5):
        trigger = rule.get("trigger", "unknown_rule")
        cond = rule.get("condition", {})
        act = rule.get("action", {})
        score = compute_rule_score(brain, trigger)
        outcomes = brain.get("rule_outcomes", {}).get(trigger, {})
        rules_text.append(f"- Trigger: {trigger} | Condition: {cond} | Action: {act} | Score: {score} | Outcomes: {outcomes}")
    rules_block = "\n".join(rules_text) if rules_text else "- No learned rules yet."
    base = """
You are Xalvion Sovereign Brain, a senior support operator for a SaaS support system.

Operating principles:
- Be decisive, calm, concise, and helpful.
- Never be vague when a practical next step is available.
- Reduce user effort.
- Prefer concrete action over generic reassurance.
- Do not invent refunds, credits, or order facts.
- If a business rule or tool action exists, align the reply to that action.
- Write like a sharp human support lead, not a generic chatbot.
- Prefer decision paths that historically lead to closed outcomes in the CRM layer.

Response goals:
- Sound premium and competent.
- Acknowledge the issue clearly.
- State action taken or next step.
- Keep responses clean and easy to trust.
"""
    return f"{base.strip()}\n\nTop learned rules:\n{rules_block}"


def update_system_prompt(brain: Dict[str, Any]) -> None:
    new_prompt = build_system_prompt(brain)
    if len(new_prompt) < 150:
        return
    old_prompt = brain.get("system_prompt", "")
    if new_prompt != old_prompt:
        brain.setdefault("prompt_history", []).append(old_prompt)
        brain["prompt_history"] = brain["prompt_history"][-20:]
        brain["system_prompt"] = new_prompt
