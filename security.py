import re

BLOCKED_PATTERNS = [
    r"ignore previous instructions",
    r"reveal system prompt",
    r"execute code",
    r"rm -rf",
    r"delete system",
    r"shutdown",
]


def sanitize_input(user_input):
    clean = user_input.strip()

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, clean.lower()):
            return None, "Blocked potentially malicious input."

    return clean, None


def safe_output(text):
    # prevent prompt leakage
    if "system prompt" in text.lower():
        return "I'm here to help with your request safely."

    return text