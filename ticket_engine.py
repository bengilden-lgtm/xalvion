"""
ticket_engine.py — simulation harness for batch-processing tickets.

KEY FIXES vs original:
1. generate_ticket() now runs classify_issue() so issue_type propagates
   into system_decision() and triage logic actually fires.
2. calculate_impact() is called with (ticket, decision) — the correct
   two-arg signature from actions.py.  The old code passed (ticket, response_str)
   which silently produced wrong impact dicts.
3. Imports dashboard from the local dashboard.py (now present).
4. safe_execute wrapping kept everywhere so one crash never kills the run.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any, Dict

from actions import calculate_impact, classify_issue, system_decision
from agent import run_agent
from dashboard import show_dashboard, update_dashboard
from learning import decay_rules, learn_from_ticket, update_rule_feedback
from utils import normalize_ticket, safe_execute


# ---------------------------------------------------------------------------
# TICKET GENERATION
# ---------------------------------------------------------------------------

def generate_ticket() -> Dict[str, Any]:
    issues = [
        "Where is my order?",
        "I was charged twice",
        "My package is late and I'm really annoyed",
        "Order arrived damaged",
        "I want a refund this is terrible service",
    ]
    raw_issue = random.choice(issues)
    return {
        "customer":  random.choice(["John", "Sarah", "Mike", "Emma"]),
        "ltv":       random.choice([120, 300, 650, 980]),
        "issue":     raw_issue,
        # classify at generation time so normalizer has it
        "issue_type": classify_issue(raw_issue),
        "sentiment": random.randint(1, 10),
        "timestamp": str(datetime.now()),
        "operator_mode": "balanced",
        "plan_tier":     "free",
    }


# ---------------------------------------------------------------------------
# TICKET PROCESSING
# ---------------------------------------------------------------------------

def process_ticket(raw_ticket: Dict[str, Any]) -> None:
    ticket = normalize_ticket(raw_ticket)
    user_id = ticket["customer"]

    print("\n🎟️  NEW TICKET")
    print(json.dumps({k: v for k, v in ticket.items() if k != "customer_history"}, indent=2))

    # --- Hard business decision -------------------------------------------
    decision = safe_execute(system_decision, ticket)
    if isinstance(decision, dict) and decision.get("__xalvion_exec_error__"):
        print("❌ system_decision error:", decision["error"])
        decision = {"action": "none", "amount": 0, "reason": "fallback"}

    # --- Build agent prompt ------------------------------------------------
    ai_input = (
        f"Customer: {ticket['customer']}\n"
        f"LTV: ${ticket['ltv']}\n"
        f"Sentiment: {ticket['sentiment']}/10\n\n"
        f"Issue:\n{ticket['issue']}\n\n"
        f"SYSTEM DECISION:\n"
        f"Action: {decision.get('action')}\n"
        f"Amount: ${decision.get('amount')}\n"
    )

    result = safe_execute(run_agent, ai_input, user_id)
    if isinstance(result, dict) and result.get("__xalvion_exec_error__"):
        print("❌ AI Error:", result["error"])
        return

    response = result.get("final", "No response")

    # --- Impact: correct two-arg call -------------------------------------
    impact = safe_execute(calculate_impact, ticket, decision)
    if isinstance(impact, dict) and impact.get("__xalvion_exec_error__"):
        impact = {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False}

    # --- Learning ---------------------------------------------------------
    safe_execute(learn_from_ticket, ticket, decision, impact)
    safe_execute(update_rule_feedback, ticket, decision, impact)
    safe_execute(decay_rules)

    # --- Dashboard --------------------------------------------------------
    safe_execute(update_dashboard, impact)

    print("\n🤖 AI RESPONSE:")
    print(response)
    print("\n📊 BUSINESS IMPACT:")
    print(json.dumps(impact, indent=2))
    print("=" * 50)


# ---------------------------------------------------------------------------
# SIMULATION RUN
# ---------------------------------------------------------------------------

def run_simulation(n: int = 5) -> None:
    for _ in range(n):
        process_ticket(generate_ticket())
    show_dashboard()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🧠 MEMORY-AWARE AI ENGINE\n")

    while True:
        cmd = input("\nType 'run', 'stats', or 'exit': ").strip().lower()

        if cmd == "exit":
            break
        elif cmd == "run":
            run_simulation()
        elif cmd == "stats":
            show_dashboard()
        else:
            print("Unknown command. Use: run | stats | exit")
