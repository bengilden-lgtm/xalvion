import json
import os

BILLING_FILE = "billing.json"


# 📂 LOAD
def load_billing():
    if not os.path.exists(BILLING_FILE):
        return {}

    with open(BILLING_FILE, "r") as f:
        return json.load(f)


# 💾 SAVE
def save_billing(data):
    with open(BILLING_FILE, "w") as f:
        json.dump(data, f, indent=2)


# 🧠 DEFAULT TIERS
TIERS = {
    "free": {"limit": 20},
    "pro": {"limit": 200},
    "elite": {"limit": 1000}
}


# 🆕 CREATE USER PLAN
def init_user_plan(username):
    data = load_billing()

    if username not in data:
        data[username] = {
            "tier": "free",
            "usage": 0
        }

    save_billing(data)


# 📊 CHECK LIMIT
def check_limit(username):
    data = load_billing()

    if username not in data:
        init_user_plan(username)
        return True

    tier = data[username]["tier"]
    usage = data[username]["usage"]

    if usage >= TIERS[tier]["limit"]:
        return False

    return True


# ➕ INCREMENT USAGE
def increment_usage(username):
    data = load_billing()

    if username not in data:
        init_user_plan(username)

    data[username]["usage"] += 1
    save_billing(data)


# 🔼 UPGRADE PLAN
def upgrade_user(username, new_tier):
    data = load_billing()

    if new_tier not in TIERS:
        return {"error": "Invalid tier"}

    data[username]["tier"] = new_tier
    save_billing(data)

    return {"message": f"Upgraded to {new_tier}"}