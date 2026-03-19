import random
from learning import apply_learned_rules


def ensure_ticket_dict(ticket):
    if isinstance(ticket, dict):
        return ticket

    if isinstance(ticket, str):
        return {
            "ltv": 0,
            "sentiment": 5,
            "issue": ticket.lower()
        }

    return {}


def system_decision(ticket):
    ticket = ensure_ticket_dict(ticket)

    # 🧠 APPLY LEARNED RULES FIRST
    learned = apply_learned_rules(ticket)
    if learned:
        return {
            "action": learned["type"],
            "amount": learned["amount"]
        }

    ltv = ticket.get("ltv", 0)
    sentiment = ticket.get("sentiment", 10)
    issue = ticket.get("issue", "").lower()

    decision = {"action": "none", "amount": 0}

    if ltv > 500 and sentiment <= 3:
        decision["action"] = "credit"
        decision["amount"] = min(50, int(ltv * 0.05))
        return decision

    if sentiment <= 3:
        decision["action"] = "credit"
        decision["amount"] = 20
        return decision

    if any(word in issue for word in ["charged twice", "double charge", "damaged"]):
        decision["action"] = "refund"
        decision["amount"] = 25
        return decision

    if "late" in issue:
        return decision

    return decision


def calculate_impact(ticket, response=None, *args, **kwargs):
    ticket = ensure_ticket_dict(ticket)
    decision = system_decision(ticket)

    if decision["action"] == "refund":
        return {"type": "refund", "amount": decision["amount"]}

    if decision["action"] == "credit":
        return {"type": "credit", "amount": decision["amount"]}

    return {"type": "saved", "amount": random.randint(20, 80)}