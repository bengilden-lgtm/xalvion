from __future__ import annotations

import json
import os
from typing import Any, Dict, List

FILE = "brain.json"


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
        "system_prompt": "",
        "prompt_history": [],
    }


def save_brain(brain: Dict[str, Any]) -> None:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=2)


def normalize_rule(rule: Any) -> Dict[str, Any] | None:
    if isinstance(rule, dict):
        trigger = str(rule.get("trigger", "")).strip() or "unknown_rule"
        condition = rule.get("condition", {})
        action = rule.get("action", {"type": "none", "amount": 0})

        if not isinstance(condition, dict):
            condition = {}
        if not isinstance(action, dict):
            action = {"type": "none", "amount": 0}

        return {
            "trigger": trigger,
            "condition": condition,
            "action": {
                "type": str(action.get("type", "none")),
                "amount": int(action.get("amount", 0) or 0),
            },
        }

    if isinstance(rule, str):
        text = rule.strip()
        if not text:
            return None

        lowered = text.lower()

        if "frustration" in lowered or "empat" in lowered:
            return {
                "trigger": "frustration_empathy",
                "condition": {"sentiment_lte": 4},
                "action": {"type": "credit", "amount": 10},
            }

        if "vague" in lowered or "direct" in lowered:
            return {
                "trigger": "direct_actionable_response",
                "condition": {"sentiment_lte": 6},
                "action": {"type": "none", "amount": 0},
            }

        if "clarity" in lowered or "confident tone" in lowered:
            return {
                "trigger": "clarity_confidence_rule",
                "condition": {},
                "action": {"type": "none", "amount": 0},
            }

        return {
            "trigger": text[:50].lower().replace(" ", "_"),
            "condition": {},
            "action": {"type": "none", "amount": 0},
        }

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

    if not isinstance(brain.get("prompt_history"), list):
        brain["prompt_history"] = []

    for rule in brain["learned_rules"]:
        trigger = rule["trigger"]
        brain["rule_weights"].setdefault(trigger, 1)
        brain["rule_scores"].setdefault(trigger, 1.0)

    return brain


def load_brain() -> Dict[str, Any]:
    if not os.path.exists(FILE):
        brain = default_brain()
        update_system_prompt(brain)
        save_brain(brain)
        return brain

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            brain = json.load(f)
            if not isinstance(brain, dict):
                brain = default_brain()
    except Exception:
        brain = default_brain()

    brain = normalize_brain(brain)

    if not brain.get("system_prompt"):
        update_system_prompt(brain)

    save_brain(brain)
    return brain


def get_top_rule_objects(brain: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    scored = []

    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
        score = float(brain.get("rule_scores", {}).get(trigger, 1.0))
        scored.append((score, rule))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [rule for _, rule in scored[:limit]]


def add_rule(brain: Dict[str, Any], rule: Dict[str, Any]) -> None:
    normalized = normalize_rule(rule)
    if not normalized:
        return

    trigger = normalized["trigger"]
    existing = next((r for r in brain["learned_rules"] if r.get("trigger") == trigger), None)

    if existing is None:
        brain["learned_rules"].append(normalized)
        brain["rule_weights"][trigger] = 1
        brain["rule_scores"][trigger] = 1.0
    else:
        brain["rule_weights"][trigger] = brain["rule_weights"].get(trigger, 1) + 1
        brain["rule_scores"][trigger] = round(brain["rule_scores"].get(trigger, 1.0) + 0.2, 4)

    update_system_prompt(brain)
    save_brain(brain)


def decay_rules(brain: Dict[str, Any]) -> None:
    to_remove = []

    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
        current = float(brain["rule_scores"].get(trigger, 1.0)) * 0.99
        brain["rule_scores"][trigger] = round(current, 4)

        if current < 0.30:
            to_remove.append(trigger)

    if to_remove:
        brain["learned_rules"] = [r for r in brain["learned_rules"] if r.get("trigger") not in to_remove]
        for trigger in to_remove:
            brain["rule_scores"].pop(trigger, None)
            brain["rule_weights"].pop(trigger, None)

    update_system_prompt(brain)
    save_brain(brain)


def build_system_prompt(brain: Dict[str, Any]) -> str:
    rules_text = []

    for rule in get_top_rule_objects(brain, 5):
        trigger = rule.get("trigger", "unknown_rule")
        cond = rule.get("condition", {})
        act = rule.get("action", {})
        rules_text.append(f"- Trigger: {trigger} | Condition: {cond} | Action: {act}")

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