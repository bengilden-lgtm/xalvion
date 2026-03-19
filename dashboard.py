import json
import os

DASHBOARD_FILE = "dashboard.json"


# 📂 LOAD DATA
def load_dashboard():
    if not os.path.exists(DASHBOARD_FILE):
        return {
            "tickets": 0,
            "saved": 0,
            "refunds": 0,
            "credits": 0,
            "profit": 0
        }

    with open(DASHBOARD_FILE, "r") as f:
        return json.load(f)


# 💾 SAVE DATA
def save_dashboard(data):
    with open(DASHBOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)


# 📊 UPDATE METRICS
def update_dashboard(impact):
    data = load_dashboard()

    data["tickets"] += 1

    if impact["type"] == "saved":
        data["saved"] += impact["amount"]
        data["profit"] += impact["amount"]

    elif impact["type"] == "refund":
        data["refunds"] += impact["amount"]
        data["profit"] -= impact["amount"]

    elif impact["type"] == "credit":
        data["credits"] += impact["amount"]
        data["profit"] -= impact["amount"] * 0.5  # credits cost less than refunds

    save_dashboard(data)


# 📈 DISPLAY DASHBOARD
def show_dashboard():
    data = load_dashboard()

    print("\n📊 AI PERFORMANCE DASHBOARD")
    print("=" * 40)
    print(f"Tickets Processed: {data['tickets']}")
    print(f"💰 Total Saved: ${data['saved']}")
    print(f"💸 Total Refunds: ${data['refunds']}")
    print(f"🎁 Total Credits: ${data['credits']}")
    print("-" * 40)
    print(f"📈 Net Profit Impact: ${data['profit']}")
    print("=" * 40)