import json
import os

MEMORY_FILE = "memory.json"


# 📂 LOAD MEMORY
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}

    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


# 💾 SAVE MEMORY
def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# 🧠 GET USER MEMORY
def get_user_memory(user_id):
    memory = load_memory()
    return memory.get(user_id, {
        "history": [],
        "soul_file": "",
        "sentiment_avg": 5
    })


# 📝 UPDATE MEMORY
def update_memory(user_id, ticket, response):
    memory = load_memory()

    user_data = memory.get(user_id, {
        "history": [],
        "soul_file": "",
        "sentiment_avg": 5
    })

    # ADD TO HISTORY
    user_data["history"].append({
        "issue": ticket["issue"],
        "sentiment": ticket["sentiment"],
        "response": response
    })

    # LIMIT HISTORY (COST CONTROL)
    if len(user_data["history"]) > 10:
        user_data["history"] = user_data["history"][-10:]

    # UPDATE SENTIMENT AVERAGE
    sentiments = [h["sentiment"] for h in user_data["history"]]
    user_data["sentiment_avg"] = sum(sentiments) / len(sentiments)

    # 🧠 SOUL FILE (COMPRESSED MEMORY)
    user_data["soul_file"] = generate_soul_file(user_data)

    memory[user_id] = user_data
    save_memory(memory)


# 🧠 SOUL FILE GENERATOR
def generate_soul_file(user_data):
    issues = [h["issue"] for h in user_data["history"][-5:]]
    avg_sentiment = round(user_data["sentiment_avg"], 2)

    return f"""
User has recent issues: {issues}
Average sentiment: {avg_sentiment}/10

Behavior pattern:
- {"Frustrated user" if avg_sentiment < 4 else "Neutral/Positive user"}

Focus:
- Resolve issues quickly
- Maintain trust
"""