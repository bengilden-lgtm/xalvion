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