import json
import random
from datetime import datetime

from agent import run_agent
from actions import calculate_impact, system_decision
from learning import learn_from_ticket, update_rule_feedback, decay_rules
from dashboard import update_dashboard, show_dashboard
from utils import normalize_ticket, safe_execute


def generate_ticket():
    issues = [
        "Where is my order?",
        "I was charged twice",
        "My package is late and I'm really annoyed",
        "Order arrived damaged",
        "I want a refund this is terrible service"
    ]

    return {
        "customer": random.choice(["John", "Sarah", "Mike", "Emma"]),
        "ltv": random.choice([120, 300, 650, 980]),
        "issue": random.choice(issues),
        "sentiment": random.randint(1, 10),
        "timestamp": str(datetime.now())
    }


def process_ticket(raw_ticket):
    ticket = normalize_ticket(raw_ticket)

    user_id = ticket["customer"]

    print("\n🎟️ NEW TICKET")
    print(json.dumps(ticket, indent=2))

    decision = safe_execute(system_decision, ticket)

    ai_input = f"""
Customer: {ticket['customer']}
LTV: ${ticket['ltv']}
Sentiment: {ticket['sentiment']}/10

Issue:
{ticket['issue']}

SYSTEM DECISION:
Action: {decision.get('action')}
Amount: ${decision.get('amount')}
"""

    result = safe_execute(run_agent, ai_input, user_id)

    if isinstance(result, dict) and "error" in result:
        print("❌ AI Error:", result["error"])
        return

    response = result.get("final", "No response")

    impact = safe_execute(calculate_impact, ticket, response)

    # 🧠 LEARNING
    safe_execute(learn_from_ticket, ticket, decision, impact)
    safe_execute(update_rule_feedback, ticket, decision, impact)
    safe_execute(decay_rules)

    # 📊 DASHBOARD
    safe_execute(update_dashboard, impact)

    print("\n🤖 AI RESPONSE:")
    print(response)

    print("\n📊 BUSINESS IMPACT:")
    print(impact)

    print("=" * 50)


def run_simulation():
    for _ in range(5):
        process_ticket(generate_ticket())

    show_dashboard()


if __name__ == "__main__":
    print("🧠 MEMORY-AWARE AI ENGINE\n")

    while True:
        cmd = input("\nType 'run', 'stats', or 'exit': ")

        if cmd == "exit":
            break
        elif cmd == "run":
            run_simulation()
        elif cmd == "stats":
            show_dashboard()