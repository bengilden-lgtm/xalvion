def audit_tickets(memory):
    angry = [m for m in memory if "angry" in m["user"].lower()]

    if not angry:
        return None

    return "New Rule: Be more empathetic in early responses."