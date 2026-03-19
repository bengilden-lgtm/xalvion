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
            "final": f"Fallback response: {message}",
            "confidence": 0.1,
            "quality": 0.1,
            "mode": "error",
            "error": str(e)
        }