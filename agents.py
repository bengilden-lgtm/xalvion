def run_agent(message: str):
    try:
        from agents import process_message

        result = process_message(message)

        return {
            "final": result.get("final", "No response"),
            "confidence": result.get("confidence", 0.5),
            "quality": result.get("quality", 0.5),
            "mode": result.get("mode", "unknown")
        }

    except Exception as e:
        return {
            "final": f"ERROR: {str(e)}",
            "confidence": 0,
            "quality": 0,
            "mode": "debug"
        }
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