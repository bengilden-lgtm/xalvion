def process_message(message: str):
    message = message.lower()

    if "hello" in message:
        return {
            "final": "Hey — I’m alive and thinking.",
            "confidence": 0.9,
            "quality": 0.9,
            "mode": "friendly"
        }

    if "help" in message:
        return {
            "final": "I can help you. Ask me anything.",
            "confidence": 0.8,
            "quality": 0.8,
            "mode": "assist"
        }

    return {
        "final": f"I understand: {message}",
        "confidence": 0.7,
        "quality": 0.7,
        "mode": "default"
    }