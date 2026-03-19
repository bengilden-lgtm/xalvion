import json
import os
import time

RULES_FILE = "learned_rules.json"


# 📂 LOAD RULES
def load_rules():
    if not os.path.exists(RULES_FILE):
        return []

    with open(RULES_FILE, "r") as f:
        return json.load(f)


# 💾 SAVE RULES
def save_rules(rules):
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)


# 🛡️ VALIDATE RULE
def validate_rule(rule):
    amount = rule["action"].get("amount", 0)

    if amount > 50:
        return False

    if not rule.get("condition"):
        return False

    if rule["action"]["type"] == "refund":
        return False

    return True


# 🧪 SIMULATE RULE
def simulate_rule(rule):
    test_cases = [
        {"ltv": 100, "sentiment": 8},
        {"ltv": 900, "sentiment": 2},
        {"ltv": 300, "sentiment": 5},
    ]

    for test in test_cases:
        if "sentiment" in rule["condition"]:
            if test["sentiment"] > 5 and rule["action"]["amount"] > 20:
                return False

    return True


# 🧠 LEARNING ENGINE
def learn_from_ticket(ticket, decision, outcome):
    rules = load_rules()

    sentiment = ticket.get("sentiment", 5)
    ltv = ticket.get("ltv", 0)

    candidate = None

    if sentiment <= 3 and decision["action"] == "none":
        candidate = {
            "trigger": "low_sentiment_no_action",
            "condition": {"sentiment": "<=3"},
            "action": {"type": "credit", "amount": 15},
            "weight": 1.0,
            "last_used": time.time()
        }

    if ltv > 800 and decision["action"] == "none":
        candidate = {
            "trigger": "high_ltv_protection",
            "condition": {"ltv": ">800"},
            "action": {"type": "credit", "amount": 30},
            "weight": 1.0,
            "last_used": time.time()
        }

    if not candidate:
        return

    print("\n🧠 Candidate Rule:", candidate["trigger"])

    if not validate_rule(candidate):
        print("🚫 Failed validation")
        return

    if not simulate_rule(candidate):
        print("🚫 Failed simulation")
        return

    # CHECK EXISTING RULE
    for rule in rules:
        if rule["trigger"] == candidate["trigger"]:
            print("🔁 Reinforcing existing rule")
            rule["weight"] += 0.5
            rule["last_used"] = time.time()
            save_rules(rules)
            return

    print("✅ New rule learned")
    rules.append(candidate)
    save_rules(rules)


# ⚙️ APPLY RULES (WEIGHTED)
def apply_learned_rules(ticket):
    rules = load_rules()

    if not rules:
        return None

    # SORT BY WEIGHT (STRONGEST FIRST)
    rules = sorted(rules, key=lambda x: x.get("weight", 0), reverse=True)

    for rule in rules:
        cond = rule["condition"]

        if "sentiment" in cond:
            if ticket.get("sentiment", 10) <= 3:
                rule["last_used"] = time.time()
                save_rules(rules)
                return rule["action"]

        if "ltv" in cond:
            if ticket.get("ltv", 0) > 800:
                rule["last_used"] = time.time()
                save_rules(rules)
                return rule["action"]

    return None


# 🧠 FEEDBACK LOOP (CRITICAL)
def update_rule_feedback(ticket, decision, outcome):
    rules = load_rules()

    for rule in rules:
        # MATCH RULE
        if rule["trigger"] == "low_sentiment_no_action":
            if ticket.get("sentiment", 10) <= 3:

                if outcome["type"] == "credit":
                    rule["weight"] += 0.3  # good outcome
                else:
                    rule["weight"] -= 0.5  # bad outcome

        if rule["trigger"] == "high_ltv_protection":
            if ticket.get("ltv", 0) > 800:

                if outcome["type"] == "credit":
                    rule["weight"] += 0.3
                else:
                    rule["weight"] -= 0.5

    save_rules(rules)


# 🧹 DECAY SYSTEM (FORGET BAD RULES)
def decay_rules():
    rules = load_rules()
    now = time.time()

    updated_rules = []

    for rule in rules:
        age = now - rule.get("last_used", now)

        # ⏳ decay over time
        if age > 60:  # seconds (for testing, increase later)
            rule["weight"] -= 0.1

        # ❌ remove weak rules
        if rule["weight"] > 0:
            updated_rules.append(rule)
        else:
            print(f"🗑️ Removed weak rule: {rule['trigger']}")

    save_rules(updated_rules)