def detect_pattern(memory):
    if len(memory) < 3:
        return None

    last = [m["user"].lower() for m in memory[-3:]]

    if len(set(last)) == 1:
        return "loop"

    for m in memory:
        if "refund" in m["user"].lower() and "can't" in m["ai"].lower():
            return "policy_conflict"

    for m in memory:
        if "angry" in m["user"].lower():
            return "frustration"

    return None


def generate_rule(pattern):
    if pattern == "loop":
        return "Always provide a clearer, more direct answer when a user repeats themselves."

    if pattern == "policy_conflict":
        return "When denying a request, always offer a strong alternative solution."

    if pattern == "frustration":
        return "When a user shows frustration, lead with empathy and immediate action."

    return None