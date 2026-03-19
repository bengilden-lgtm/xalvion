import json
import os
from datetime import datetime

FILE = "analytics.json"


def load_analytics():
    if not os.path.exists(FILE):
        return []

    with open(FILE, "r") as f:
        return json.load(f)


def log_event(user_input, response, confidence, quality):
    data = load_analytics()

    event = {
        "time": str(datetime.now()),
        "input": user_input,
        "confidence": confidence,
        "quality": quality,
        "length": len(response)
    }

    data.append(event)
    data = data[-1000:]

    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_metrics():
    data = load_analytics()

    if not data:
        return {}

    avg_conf = sum(d["confidence"] for d in data) / len(data)
    avg_quality = sum(d["quality"] for d in data) / len(data)

    return {
        "avg_confidence": round(avg_conf, 2),
        "avg_quality": round(avg_quality, 2),
        "total_interactions": len(data)
    }