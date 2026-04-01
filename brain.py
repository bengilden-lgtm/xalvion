from __future__ import annotations

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
    if not isinstance(brain.get("prompt_history"), list):
        brain["prompt_history"] = []
    for rule in brain["learned_rules"]:
        trigger = rule["trigger"]
        brain["rule_weights"].setdefault(trigger, 1)
        brain["rule_scores"].setdefault(trigger, 1.0)
        brain["rule_outcomes"].setdefault(trigger, {"wins": 0, "losses": 0, "closed_wins": 0})
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
    return round(base + (weight * 0.12) + (wins * 0.18) + conversion_bonus - penalty, 4)


def get_top_rule_objects(brain: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    scored = []
    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
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
    else:
        brain["rule_weights"][trigger] = brain["rule_weights"].get(trigger, 1) + 1
        brain["rule_scores"][trigger] = round(brain["rule_scores"].get(trigger, 1.0) + 0.2, 4)
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


def decay_rules(brain: Dict[str, Any]) -> None:
    to_remove = []
    for rule in brain.get("learned_rules", []):
        trigger = rule.get("trigger", "unknown_rule")
        current = float(brain["rule_scores"].get(trigger, 1.0)) * 0.992
        brain["rule_scores"][trigger] = round(current, 4)
        if current < 0.30:
            to_remove.append(trigger)
    if to_remove:
        brain["learned_rules"] = [r for r in brain["learned_rules"] if r.get("trigger") not in to_remove]
        for trigger in to_remove:
            brain["rule_scores"].pop(trigger, None)
            brain["rule_weights"].pop(trigger, None)
            brain["rule_outcomes"].pop(trigger, None)
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
