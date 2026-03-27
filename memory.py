from __future__ import annotations

import json
import os
import time
from collections import Counter
from typing import Any, Dict, List

MEMORY_FILE = "memory.json"
MAX_HISTORY = 40


def _now() -> float:
    return time.time()


def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_FILE):
        return {}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def _default_user_memory() -> Dict[str, Any]:
    return {
        "history": [],
        "soul_file": "",
        "sentiment_avg": 5.0,
        "refund_count": 0,
        "credit_count": 0,
        "review_count": 0,
        "complaint_count": 0,
        "issue_counts": {},
        "last_issue_type": "general_support",
        "ltv_high_watermark": 0,
        "plan_tier": "free",
        "abuse_score": 0,
        "repeat_customer": False,
        "last_updated": 0,
    }


def calculate_importance(message: str, sentiment: int, action: str = "none") -> float:
    text = (message or "").lower()
    score = 1.0

    if sentiment <= 3:
        score += 2.0
    elif sentiment <= 5:
        score += 1.0

    keywords = [
        "refund",
        "charged twice",
        "stress",
        "angry",
        "frustrated",
        "annoyed",
        "damaged",
        "late",
        "not working",
        "error",
        "urgent",
    ]
    if any(k in text for k in keywords):
        score += 2.0

    if action in {"refund", "review"}:
        score += 1.5
    if len(text) > 80:
        score += 1.0

    return score


def apply_decay(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = _now()

    for item in history:
        age = max(0.0, now - float(item.get("timestamp", now)))
        decay_factor = max(0.55, 1.0 - (age / 320000.0))
        item["importance"] = round(float(item.get("importance", 1.0)) * decay_factor, 4)

    return history


def get_top_memories(history: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return sorted(history, key=lambda x: float(x.get("importance", 1.0)), reverse=True)[:limit]


def _rebuild_user_metrics(user_data: Dict[str, Any]) -> Dict[str, Any]:
    history = user_data.get("history", [])
    sentiments = [float(h.get("sentiment", 5)) for h in history] or [5.0]
    issue_counter = Counter(str(h.get("issue_type", "general_support")) for h in history if h.get("issue_type"))
    refund_count = sum(1 for h in history if str(h.get("action", "none")) == "refund")
    credit_count = sum(1 for h in history if str(h.get("action", "none")) == "credit")
    review_count = sum(1 for h in history if str(h.get("action", "none")) == "review")
    complaint_count = sum(1 for h in history if int(h.get("sentiment", 5) or 5) <= 4)
    repeated_refund_requests = sum(1 for h in history if str(h.get("issue_type", "")) in {"refund_request", "billing_duplicate_charge"})

    abuse_score = 0
    if refund_count >= 3:
        abuse_score += 1
    if repeated_refund_requests >= 4:
        abuse_score += 1
    if review_count >= 3:
        abuse_score += 1
    if complaint_count >= 5:
        abuse_score += 1

    user_data["sentiment_avg"] = round(sum(sentiments) / len(sentiments), 2)
    user_data["refund_count"] = refund_count
    user_data["credit_count"] = credit_count
    user_data["review_count"] = review_count
    user_data["complaint_count"] = complaint_count
    user_data["issue_counts"] = dict(issue_counter)
    user_data["abuse_score"] = abuse_score
    user_data["repeat_customer"] = len(history) >= 2
    if history:
        user_data["last_issue_type"] = str(history[-1].get("issue_type", "general_support"))
    return user_data


def generate_soul_file(user_data: Dict[str, Any]) -> str:
    history = user_data.get("history", [])
    top = get_top_memories(history, 5)

    top_issues = [h.get("issue", "") for h in top if h.get("issue")]
    avg_sentiment = round(float(user_data.get("sentiment_avg", 5.0)), 2)
    refund_count = int(user_data.get("refund_count", 0) or 0)
    complaint_count = int(user_data.get("complaint_count", 0) or 0)
    abuse_score = int(user_data.get("abuse_score", 0) or 0)
    plan_tier = str(user_data.get("plan_tier", "free") or "free").title()
    ltv = int(user_data.get("ltv_high_watermark", 0) or 0)

    profile_lines = []
    if avg_sentiment <= 3.5:
        profile_lines.append("- Often frustrated or under pressure")
    elif avg_sentiment <= 6.5:
        profile_lines.append("- Mixed emotional baseline")
    else:
        profile_lines.append("- Generally stable")

    if ltv >= 500:
        profile_lines.append("- High-value customer history detected")
    if refund_count >= 3:
        profile_lines.append("- Repeat refund pattern present; verify before auto-refunding")
    if complaint_count >= 4:
        profile_lines.append("- Repeated complaints suggest churn risk")
    if abuse_score >= 2:
        profile_lines.append("- Abuse/fraud caution flags are elevated")

    profile_lines.append("- Responds best to clear, direct help")
    profile_lines.append("- Reduce effort and avoid vague answers")

    joined_issues = "\n".join(f"- {issue}" for issue in top_issues[:5]) if top_issues else "- No major repeated issues yet"

    return (
        "User Memory Summary\n"
        f"Plan tier: {plan_tier}\n"
        f"Emotional baseline: {avg_sentiment}/10\n"
        f"Highest LTV seen: ${ltv}\n"
        f"Refund count: {refund_count} | Complaints: {complaint_count} | Abuse score: {abuse_score}\n\n"
        "Repeated themes:\n"
        f"{joined_issues}\n\n"
        "Response style guidance:\n"
        + "\n".join(profile_lines)
    )


def get_user_memory(user_id: str) -> Dict[str, Any]:
    memory = load_memory()
    user_data = memory.get(user_id, _default_user_memory())
    merged = _default_user_memory()
    merged.update(user_data if isinstance(user_data, dict) else {})
    merged = _rebuild_user_metrics(merged)
    merged["soul_file"] = generate_soul_file(merged)
    return merged


def update_memory(user_id: str, ticket: Dict[str, Any], response: str, decision: Dict[str, Any] | None = None) -> None:
    memory = load_memory()
    user_data = get_user_memory(user_id)
    decision = decision or {}

    issue = str(ticket.get("issue", "")).strip()
    sentiment = int(ticket.get("sentiment", 5) or 5)
    action = str(decision.get("action", ticket.get("action", "none")) or "none")
    amount = int(decision.get("amount", 0) or 0)
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    ltv = int(ticket.get("ltv", 0) or 0)

    entry = {
        "issue": issue,
        "issue_type": issue_type,
        "sentiment": sentiment,
        "response": response,
        "action": action,
        "amount": amount,
        "importance": calculate_importance(issue, sentiment, action),
        "timestamp": _now(),
    }

    user_data["history"].append(entry)
    user_data["history"] = apply_decay(user_data["history"])[-MAX_HISTORY:]
    user_data["ltv_high_watermark"] = max(int(user_data.get("ltv_high_watermark", 0) or 0), ltv)
    user_data["plan_tier"] = str(ticket.get("plan_tier", user_data.get("plan_tier", "free")) or "free")
    user_data["last_updated"] = _now()

    user_data = _rebuild_user_metrics(user_data)
    user_data["soul_file"] = generate_soul_file(user_data)

    memory[user_id] = user_data
    save_memory(memory)


def get_prompt_memory(user_id: str, limit: int = 5) -> str:
    user_data = get_user_memory(user_id)
    history = user_data.get("history", [])
    top = get_top_memories(history, limit)

    if not top:
        return "No important prior memory."

    lines = []
    for item in top:
        lines.append(
            f"- Issue: {item.get('issue', '')} | "
            f"Type: {item.get('issue_type', 'general_support')} | "
            f"Sentiment: {item.get('sentiment', 5)} | "
            f"Action: {item.get('action', 'none')} | "
            f"Importance: {item.get('importance', 1.0)}"
        )

    return "\n".join(lines)
