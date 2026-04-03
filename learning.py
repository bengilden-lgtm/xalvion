from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from brain import add_rule, get_top_rule_objects, load_brain, register_rule_outcome, save_brain

try:
    from outcome_store import get_outcome
except Exception:
    def get_outcome(outcome_key):
        return None

RULES_FILE = "learned_rules.json"


def load_rules() -> List[Dict[str, Any]]:
    if not os.path.exists(RULES_FILE):
        return []
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_rules(rules: List[Dict[str, Any]]) -> None:
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


def validate_rule(rule: Dict[str, Any]) -> bool:
    amount = int(rule["action"].get("amount", 0) or 0)
    if amount > 50:
        return False
    condition = rule.get("condition")
    if condition is None or not isinstance(condition, dict):
        return False
    if rule["action"].get("type") == "refund":
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


def _score_outcome(outcome: Dict[str, Any], outcome_key: str | None = None) -> float:
    """
    Score an outcome.  If a real outcome exists in outcome_store, use it.
    Falls back to the self-reported outcome dict for backwards compatibility.
    """
    real: Dict[str, Any] | None = None
    if outcome_key:
        try:
            real = get_outcome(outcome_key)
        except Exception:
            real = None

    score = 0.0

    if real is not None:
        # Real outcome path — use verified API result
        if real.get("success"):
            score += 2.5
        if real.get("auto_resolved"):
            score += 1.0
        if real.get("approved_by_human"):
            score += 0.5
        if real.get("refund_reversed") or real.get("dispute_filed"):
            score -= 3.0  # strong negative signal — rule was wrong
    else:
        # Self-reported fallback — original logic preserved
        if _is_closed_outcome(outcome):
            score += 2.0
        if bool(outcome.get("auto_resolved", False)):
            score += 1.0
        score += min(2.0, float(outcome.get("money_saved", 0.0) or 0.0) / 50.0)
        score += min(1.0, float(outcome.get("agent_minutes_saved", 0) or 0) / 10.0)

    return round(score, 4)


def learn_from_ticket(ticket: Dict[str, Any], decision: Dict[str, Any], outcome: Dict[str, Any], outcome_key: str | None = None) -> None:
    rules = load_rules()
    candidate = _candidate_rule(ticket, decision)
    if not candidate:
        return
    if not validate_rule(candidate) or not simulate_rule(candidate):
        return
    conversion_weight = 1.0 + _score_outcome(outcome, outcome_key=outcome_key)
    for rule in rules:
        if rule["trigger"] == candidate["trigger"]:
            rule["weight"] = round(float(rule.get("weight", 1.0)) + (0.5 * conversion_weight), 4)
            rule["last_used"] = time.time()
            save_rules(rules)
            brain = load_brain()
            add_rule(brain, candidate)
            register_rule_outcome(brain, candidate["trigger"], closed=_is_closed_outcome(outcome), positive=True)
            return
    candidate["weight"] = round(max(0.05, conversion_weight), 4)
    rules.append(candidate)
    save_rules(rules)
    brain = load_brain()
    add_rule(brain, candidate)
    register_rule_outcome(brain, candidate["trigger"], closed=_is_closed_outcome(outcome), positive=True)


def apply_learned_rules(ticket: Dict[str, Any], top_rules: List[Dict[str, Any]] | None = None) -> Dict[str, Any] | None:
    if top_rules is not None:
        rules = top_rules
    else:
        try:
            brain = load_brain()
            rules = get_top_rule_objects(brain, 10)
            if not rules:
                rules = load_rules()
        except Exception:
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
    success = _score_outcome(outcome) > 0.9
    for rule in rules:
        trigger = rule.get("trigger", "")
        matches_low_sentiment = trigger == "low_sentiment_no_action" and int(ticket.get("sentiment", 10) or 10) <= 3
        matches_high_ltv = trigger == "high_ltv_protection" and int(ticket.get("ltv", 0) or 0) > 800
        if matches_low_sentiment or matches_high_ltv:
            delta = 0.35 if success else -0.45
            if decision_action == "credit" and _is_closed_outcome(outcome):
                delta += 0.55
            rule["weight"] = round(max(0.0, float(rule.get("weight", 1.0)) + delta), 4)
            rule["last_used"] = time.time()
            brain = load_brain()
            register_rule_outcome(brain, trigger, closed=_is_closed_outcome(outcome), positive=success)
            save_brain(brain)
    save_rules(rules)


def sync_rules_to_brain() -> None:
    """
    One-way sync on startup: push rules from learned_rules.json
    into brain state if brain is missing them. Safe to call multiple
    times — add_rule() is idempotent for existing triggers.
    """
    rules = load_rules()
    if not rules:
        return
    try:
        brain = load_brain()
        for rule in rules:
            trigger = rule.get("trigger", "")
            if not trigger:
                continue
            already_in_brain = any(
                r.get("trigger") == trigger for r in brain.get("learned_rules", [])
            )
            if not already_in_brain:
                add_rule(brain, rule)
    except Exception:
        pass


def decay_rules() -> None:
    rules = load_rules()
    now = time.time()
    updated: List[Dict[str, Any]] = []
    for rule in rules:
        age = now - float(rule.get("last_used", now))
        if age > 86400:
            rule["weight"] = round(float(rule.get("weight", 1.0)) - 0.1, 4)
        if float(rule.get("weight", 0)) > 0:
            updated.append(rule)
    save_rules(updated)
