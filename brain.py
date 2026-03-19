import json
import os

FILE = "brain.json"


def default_brain():
    return {
        "core_knowledge": [],
        "soul_file": "",
        "learned_rules": [],
        "rule_weights": {},
        "rule_scores": {},
        "system_prompt": "",
        "prompt_history": []
    }


def load_brain():
    if not os.path.exists(FILE):
        brain = default_brain()
        save_brain(brain)
        return brain

    with open(FILE, "r") as f:
        brain = json.load(f)

    defaults = default_brain()

    for key in defaults:
        if key not in brain:
            brain[key] = defaults[key]

    for rule in brain["learned_rules"]:
        if rule not in brain["rule_weights"]:
            brain["rule_weights"][rule] = 1
        if rule not in brain["rule_scores"]:
            brain["rule_scores"][rule] = 1.0

    save_brain(brain)
    return brain


def save_brain(brain):
    with open(FILE, "w") as f:
        json.dump(brain, f, indent=2)


def update_soul(brain, text):
    brain["soul_file"] = text[:500]
    save_brain(brain)


def add_rule(brain, rule):
    if rule not in brain["learned_rules"]:
        brain["learned_rules"].append(rule)
        brain["rule_weights"][rule] = 1
        brain["rule_scores"][rule] = 1.0
    else:
        brain["rule_weights"][rule] += 1
        brain["rule_scores"][rule] += 0.2

    save_brain(brain)


def decay_rules(brain):
    for rule in list(brain["rule_scores"].keys()):
        brain["rule_scores"][rule] *= 0.98

        if brain["rule_scores"][rule] < 0.3:
            brain["learned_rules"].remove(rule)
            del brain["rule_scores"][rule]
            del brain["rule_weights"][rule]

    save_brain(brain)


def get_top_rules(brain):
    sorted_rules = sorted(
        brain["rule_scores"].items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [r[0] for r in sorted_rules[:5]]


def build_system_prompt(brain):
    base = """
You are part of a Sovereign Support Engine.

You operate as a senior human support teammate:
- proactive
- decisive
- solution-oriented

Rules:
- Never say you are an AI
- Always take action when possible
- Reduce user effort
- Speak with confidence

Tone:
Professional, calm, and results-driven.
"""

    learned = "\n".join(get_top_rules(brain))

    return f"{base}\n\nLearned Behavior Rules:\n{learned}"


def update_system_prompt(brain):
    new_prompt = build_system_prompt(brain)

    # 🛡️ ROLLBACK PROTECTION
    if len(new_prompt) < 100:
        return  # reject bad prompt

    if new_prompt != brain["system_prompt"]:
        brain["prompt_history"].append(brain["system_prompt"])
        brain["system_prompt"] = new_prompt
        save_brain(brain)