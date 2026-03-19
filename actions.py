def system_decision(ticket):
    ticket = ticket or {}

    sentiment = int(ticket.get("sentiment", 5))
    ltv = int(ticket.get("ltv", 0))

    # 🎯 HARD RULES (NO AI CONTROL)
    if "charged twice" in str(ticket.get("issue", "")).lower():
        return {"action": "refund", "amount": 25}

    if sentiment <= 2 and ltv > 500:
        return {"action": "refund", "amount": min(ltv * 0.1, 50)}

    if sentiment <= 3:
        return {"action": "credit", "amount": 20}

    return {"action": "none", "amount": 0}


def calculate_impact(ticket, response):
    decision = system_decision(ticket)

    if decision["action"] == "refund":
        return {"type": "refund", "amount": decision["amount"]}

    if decision["action"] == "credit":
        return {"type": "credit", "amount": decision["amount"]}

    return {"type": "saved", "amount": 50}