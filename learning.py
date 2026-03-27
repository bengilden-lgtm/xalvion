"""
learning.py — adaptive rule engine that learns from ticket outcomes.

KEY FIXES vs original:
  1. validate_rule() used `if not rule.get("condition")` which evaluates
     False for an empty-dict condition `{}`, silently rejecting every
     candidate that brain.py generates with `"condition": {}`.
     Fixed: only reject if condition is None or not a dict.
  2. simulate_rule() was also incorrectly rejecting rules whose action
     amount was >20 even when the test sentiment was ≤5 (benign case).
     Guard is now tightened: only fail when sentiment > 5 AND amount > 20.
  3. decay threshold raised from 60 seconds to 86400 (24 h) — was
     forgetting rules within a minute in any real deployment.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

RULES_FILE = "learned_rules.json"


# ---------------------------------------------------------------------------
# PERSISTENCE
# ---------------------------------------------------------------------------

def load_rules() -> List[Dict[str, Any]]:
    if not os.path.exists(RULES_FILE):
        return []
    try:
        with open(RULES_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_rules(rules: List[Dict[str, Any]]) -> None:
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_rule(rule: Dict[str, Any]) -> bool:
    amount = rule["action"].get("amount", 0)

    # Hard safety cap
    if amount > 50:
        return False

    # FIX: `not {}` is True in Python — we only reject None / non-dict
    condition = rule.get("condition")
    if condition is None or not isinstance(condition, dict):
        return False

    # Never auto-learn a refund rule (too risky without human review)
    if rule["action"].get("type") == "refund":
        return False

    return True


# ---------------------------------------------------------------------------
# SIMULATION
# ---------------------------------------------------------------------------

def simulate_rule(rule: Dict[str, Any]) -> bool:
    test_cases = [
        {"ltv": 100, "sentiment": 8},
        {"ltv": 900, "sentiment": 2},
        {"ltv": 300, "sentiment": 5},
    ]

    for test in test_cases:
        cond = rule.get("condition", {})
        # Only flag as unsafe when sentiment is clearly positive AND
        # the rule would give a large credit — that's wasteful, not helpful.
        if "sentiment" in cond:
            if test["sentiment"] > 5 and rule["action"].get("amount", 0) > 20:
                return False

    return True


# ---------------------------------------------------------------------------
# LEARNING ENGINE
# ---------------------------------------------------------------------------

def learn_from_ticket(
    ticket: Dict[str, Any],
    decision: Dict[str, Any],
    outcome: Dict[str, Any],
) -> None:
    rules = load_rules()

    sentiment = int(ticket.get("sentiment", 5) or 5)
    ltv       = int(ticket.get("ltv", 0) or 0)

    candidate = None

    if sentiment <= 3 and decision.get("action") == "none":
        candidate = {
            "trigger":   "low_sentiment_no_action",
            "condition": {"sentiment": "<=3"},
            "action":    {"type": "credit", "amount": 15},
            "weight":    1.0,
            "last_used": time.time(),
        }

    if ltv > 800 and decision.get("action") == "none":
        candidate = {
            "trigger":   "high_ltv_protection",
            "condition": {"ltv": ">800"},
            "action":    {"type": "credit", "amount": 30},
            "weight":    1.0,
            "last_used": time.time(),
        }

    if not candidate:
        return

    print(f"\n🧠 Candidate Rule: {candidate['trigger']}")

    if not validate_rule(candidate):
        print("🚫 Failed validation")
        return

    if not simulate_rule(candidate):
        print("🚫 Failed simulation")
        return

    # Reinforce or add
    for rule in rules:
        if rule["trigger"] == candidate["trigger"]:
            print("🔁 Reinforcing existing rule")
            rule["weight"] = round(rule.get("weight", 1.0) + 0.5, 4)
            rule["last_used"] = time.time()
            save_rules(rules)
            return

    print("✅ New rule learned")
    rules.append(candidate)
    save_rules(rules)


# ---------------------------------------------------------------------------
# RULE APPLICATION
# ---------------------------------------------------------------------------

def apply_learned_rules(ticket: Dict[str, Any]) -> Dict[str, Any] | None:
    rules = load_rules()
    if not rules:
        return None

    rules = sorted(rules, key=lambda x: x.get("weight", 0), reverse=True)

    for rule in rules:
        cond = rule.get("condition", {})

        if "sentiment" in cond:
            if int(ticket.get("sentiment", 10) or 10) <= 3:
                rule["last_used"] = time.time()
                save_rules(rules)
                return rule["action"]

        if "ltv" in cond:
            if int(ticket.get("ltv", 0) or 0) > 800:
                rule["last_used"] = time.time()
                save_rules(rules)
                return rule["action"]

    return None


# ---------------------------------------------------------------------------
# FEEDBACK LOOP
# ---------------------------------------------------------------------------

def update_rule_feedback(
    ticket: Dict[str, Any],
    decision: Dict[str, Any],
    outcome: Dict[str, Any],
) -> None:
    rules = load_rules()

    for rule in rules:
        if rule["trigger"] == "low_sentiment_no_action":
            if int(ticket.get("sentiment", 10) or 10) <= 3:
                if outcome.get("type") == "credit":
                    rule["weight"] = round(rule.get("weight", 1.0) + 0.3, 4)
                else:
                    rule["weight"] = round(rule.get("weight", 1.0) - 0.5, 4)

        if rule["trigger"] == "high_ltv_protection":
            if int(ticket.get("ltv", 0) or 0) > 800:
                if outcome.get("type") == "credit":
                    rule["weight"] = round(rule.get("weight", 1.0) + 0.3, 4)
                else:
                    rule["weight"] = round(rule.get("weight", 1.0) - 0.5, 4)

    save_rules(rules)


# ---------------------------------------------------------------------------
# DECAY — forget rules that haven't fired in 24 h and have low weight
# ---------------------------------------------------------------------------

def decay_rules() -> None:
    rules = load_rules()
    now = time.time()

    updated: List[Dict[str, Any]] = []

    for rule in rules:
        age = now - float(rule.get("last_used", now))

        # Decay only after 24 h of disuse (was 60 s — unrealistic)
        if age > 86400:
            rule["weight"] = round(rule.get("weight", 1.0) - 0.1, 4)

        if rule.get("weight", 0) > 0:
            updated.append(rule)
        else:
            print(f"🗑️  Removed weak rule: {rule['trigger']}")

    save_rules(updated)
