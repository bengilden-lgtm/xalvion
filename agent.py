from __future__ import annotations

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from actions import build_ticket, calculate_impact, apply_learned_rules, system_decision, triage_ticket
from brain import add_rule, get_top_rule_objects, load_brain, save_brain, update_system_prompt
from memory import get_prompt_memory, get_user_memory, update_memory
from router import route_task
from security import safe_output, sanitize_input
from tools import get_order, issue_credit, process_refund
from models import (
    AgentRequestContext,
    CanonicalAgentResponse,
    ImpactProjections,
    MemoryDelta,
    OutputEnvelope,
    SovereignDecision,
    ThinkingTraceStep,
    TriageMetadata,
)

try:
    from analytics import log_event
except Exception:
    def log_event(user_input, response, confidence, quality):
        return None


try:
    from feedback import process_feedback
except Exception:
    def process_feedback(user_input, response, quality):
        return None


load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4o-mini")
MODEL_EXPENSIVE = os.getenv("MODEL_EXPENSIVE", "gpt-4o-mini")

client = OpenAI(api_key=API_KEY, timeout=14.0) if API_KEY else None

ALLOWED_ACTIONS = {"none", "refund", "credit", "review", "charge"}
MAX_REFUND = 50
MAX_CREDIT = 30


def choose_model(message: str) -> str:
    tier = route_task(message)
    return MODEL_CHEAP if tier == "cheap" else MODEL_EXPENSIVE


def classify_tone(ticket: Dict[str, Any]) -> str:
    sentiment = int(ticket.get("sentiment", 5) or 5)
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    operator_mode = str(ticket.get("operator_mode", "balanced") or "balanced")

    if operator_mode == "fraud_aware":
        return "firm_precise"
    if operator_mode == "delight":
        return "warm_premium"
    if sentiment <= 2:
        return "high_empathy"
    if issue_type in {"billing_duplicate_charge", "damaged_order"}:
        return "calm_action"
    if issue_type == "shipping_issue":
        return "clear_reassuring"
    return "premium_direct"


def parse_llm_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    fallback = text or "I’ve reviewed this and I’m already on the next step."
    return {
        "customer_message": fallback,
        "action": "none",
        "amount": 0,
        "reason": "fallback_parse",
        "confidence": 0.45,
        "risk_level": "medium",
        "internal_note": "Fallback parse path used.",
        "customer_note": fallback,
        "queue": "new",
        "priority": "medium",
    }


def polish_message(message: str) -> str:
    text = (message or "").strip()

    replacements = {
        "I understand your concern about": "I checked",
        "I understand your concern regarding": "I checked",
        "I understand that": "I checked that",
        "Please let me know if you need further assistance.": "",
        "please let me know if you need further assistance.": "",
        "If you need further assistance, please let me know.": "",
        "If you need further assistance, let me know.": "",
        "currently": "",
        "Currently, ": "",
        "currently, ": "",
        "We appreciate your patience.": "",
        "Thank you for your patience.": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "  " in text:
        text = text.replace("  ", " ")

    text = text.replace("..", ".").strip()
    return text

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    # Try common mojibake repair paths. Running more than once helps when a
    # string has been mis-decoded repeatedly through different layers.
    repair_attempts = (
        ("latin1", "utf-8"),
        ("cp1252", "utf-8"),
    )
    for _ in range(2):
        changed = False
        for src_enc, dst_enc in repair_attempts:
            try:
                repaired = text.encode(src_enc).decode(dst_enc)
                if repaired != text:
                    text = repaired
                    changed = True
                    break
            except Exception:
                continue
        if not changed:
            break

    replacements = {
        "Iâve": "I’ve",
        "Iâ€™ve": "I’ve",
        "Iâve": "I’ve",
        "â€™": "’",
        "â": "’",
        "â€˜": "‘",
        "â": "‘",
        "â€œ": "“",
        "â": "“",
        "â€�": "”",
        "â": "”",
        "â€“": "–",
        "â": "–",
        "â€”": "—",
        "â": "—",
        "â€¦": "…",
        "â¦": "…",
        "Â ": " ",
        "Â": "",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text

def clamp_confidence(value: Any, fallback: float = 0.9) -> float:
    try:
        number = float(value)
    except Exception:
        number = fallback

    if number <= 0:
        number = fallback

    if number < 0.55:
        number = 0.55
    if number > 0.99:
        number = 0.99

    return round(number, 2)


def is_conversational_message(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True

    conversational_exact = {
        "hi", "hello", "hey", "heya", "yo", "sup", "wassup", "what's up", "whats up",
        "how are you", "how r u", "how are u", "who are you", "who are u", "thanks", "thank you", "thx", "cool", "nice",
    }

    if text in conversational_exact:
        return True

    support_markers = (
        "order", "package", "refund", "charged", "billing", "damaged", "late", "tracking",
        "delivered", "not working", "error", "invoice", "login", "password", "export",
        "cancel", "cancelling", "canceling", "shipping", "address", "change my shipping address",
        "double charge", "duplicate charge", "arrived", "delay", "delayed", "broken",
    )
    if any(marker in text for marker in support_markers):
        return False

    if "i'm cancel" in text or "im cancel" in text:
        return False

    return len(text.split()) <= 4


def build_structured_response(
    *,
    customer_message: str,
    action_payload: Dict[str, Any],
    ticket: Dict[str, Any],
    history: Dict[str, Any],
    triage: Dict[str, Any],
    mode: str,
    confidence: float,
    quality: float,
    tool_payload: Dict[str, Any],
    internal_note: str,
    customer_note: str,
) -> Dict[str, Any]:
    safe_action = normalize_action_payload(action_payload)
    impact = calculate_impact(ticket, safe_action)

    queue = str(action_payload.get("queue", "new") or "new")
    priority = str(action_payload.get("priority", "medium") or "medium")
    risk_level = str(action_payload.get("risk_level", triage.get("risk_level", "medium")) or "medium")

    return {
        "response": customer_message,
        "final": customer_message,
        "reply": customer_message,
        "mode": mode,
        "quality": round(float(quality or 0), 2),
        "confidence": clamp_confidence(confidence, 0.9),
        "action": safe_action["action"],
        "amount": safe_action["amount"],
        "reason": str(action_payload.get("reason", "") or ""),
        "issue_type": ticket.get("issue_type", "general_support"),
        "order_status": ticket.get("order_status", "unknown"),
        "tool_result": tool_payload.get("tool_result", {"status": "no_action"}),
        "tool_status": tool_payload.get("tool_status", "no_action"),
        "impact": impact,
        "decision": {
            "action": safe_action["action"],
            "amount": safe_action["amount"],
            "confidence": clamp_confidence(confidence, 0.9),
            "risk_level": risk_level,
            "reason": str(action_payload.get("reason", "") or ""),
            "priority": priority,
            "requires_approval": bool(action_payload.get("requires_approval", False)),
            "queue": queue,
        },
        "output": {
            "internal_note": normalize_text(internal_note),
            "customer_note": normalize_text(customer_note),
            "audit_log": f"{ticket.get('issue_type', 'general_support')} -> {safe_action['action']} (${safe_action['amount']}) | {action_payload.get('reason', '')}",
        },
        "meta": {
            "issue_type": ticket.get("issue_type", "general_support"),
            "priority": priority,
            "ltv": int(ticket.get("ltv", 0) or 0),
            "sentiment": int(ticket.get("sentiment", 5) or 5),
            "plan_tier": ticket.get("plan_tier", "free"),
            "operator_mode": ticket.get("operator_mode", "balanced"),
            "queue": queue,
        },
        "triage": triage,
        "history": {
            "refund_count": int(history.get("refund_count", 0) or 0),
            "credit_count": int(history.get("credit_count", 0) or 0),
            "review_count": int(history.get("review_count", 0) or 0),
            "complaint_count": int(history.get("complaint_count", 0) or 0),
            "abuse_score": int(history.get("abuse_score", 0) or 0),
            "repeat_customer": bool(history.get("repeat_customer", False)),
            "sentiment_avg": float(history.get("sentiment_avg", 5.0) or 5.0),
        },
    }


def conversational_reply(message: str) -> Dict[str, Any]:
    text = (message or "").strip().lower()

    if "how are you" in text or "how are u" in text:
        reply = "I’m good — online, focused, and ready to help. Drop the issue and I’ll work it through."
    elif text in {"hi", "hello", "hey", "heya", "yo", "sup", "wassup", "what's up", "whats up"} or text.startswith(("hi ", "hello ", "hey ", "yo ")):
        reply = "Hey — I’m here and ready. Send me the issue and I’ll handle it."
    elif "who are you" in text or "who are u" in text:
        reply = "I’m Xalvion — a support operator built to analyze issues, take the right action, and keep the response clear."
    elif "thanks" in text or "thank you" in text or "thx" in text:
        reply = "Any time."
    else:
        reply = "I’m here and ready. Send me the issue and I’ll handle it."

    empty_ticket = {
        "issue_type": "conversation",
        "order_status": "unknown",
        "ltv": 0,
        "sentiment": 5,
        "plan_tier": "free",
        "operator_mode": "balanced",
    }
    history = get_user_memory("conversation")
    triage = triage_ticket(empty_ticket, history)
    tool_payload = {"tool_result": {"status": "no_action"}, "tool_status": "no_action"}
    action_payload = {"action": "none", "amount": 0, "reason": "conversational_bypass", "priority": "low", "queue": "new", "risk_level": "low"}

    return build_structured_response(
        customer_message=reply,
        action_payload=action_payload,
        ticket=empty_ticket,
        history=history,
        triage=triage,
        mode="sovereign-conversation",
        confidence=0.96,
        quality=0.95,
        tool_payload=tool_payload,
        internal_note="Conversational bypass executed.",
        customer_note=reply,
    )


def should_attach_order_context(issue_type: str) -> bool:
    return issue_type in {"shipping_issue", "damaged_order"}


def normalize_action_payload(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = payload or {}
    action = str(payload.get("action", "none")).strip().lower()
    amount = int(payload.get("amount", 0) or 0)

    if action not in ALLOWED_ACTIONS:
        action = "none"

    if amount < 0:
        amount = 0

    if action == "refund":
        amount = min(amount, MAX_REFUND)
    elif action == "credit":
        amount = min(amount, MAX_CREDIT)
    elif action == "charge":
        amount = min(amount, MAX_REFUND)
    else:
        amount = 0

    return {
        "action": action,
        "amount": amount,
        "reason": str(payload.get("reason", "") or ""),
        "priority": str(payload.get("priority", "medium") or "medium"),
        "risk_level": str(payload.get("risk_level", "medium") or "medium"),
        "queue": str(payload.get("queue", "new") or "new"),
        "requires_approval": bool(payload.get("requires_approval", False)),
    }


def execute_action(ticket: Dict[str, Any], action_payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_action = normalize_action_payload(action_payload)
    action = safe_action["action"]
    amount = safe_action["amount"]
    customer = ticket.get("customer", "Unknown")

    if safe_action.get("requires_approval"):
        result = {"status": "pending_approval"}
        return {
            "action": "review",
            "amount": 0,
            "tool_result": result,
            "tool_status": result["status"],
        }

    if action == "refund":
        result = process_refund(customer, amount)
        if result.get("error"):
            return {
                "action": "review",
                "amount": 0,
                "tool_result": result,
                "tool_status": result.get("error", "error"),
            }
        return {
            "action": "refund",
            "amount": amount,
            "tool_result": result,
            "tool_status": result.get("status", "success"),
        }

    if action == "credit":
        result = issue_credit(customer, amount)
        return {
            "action": "credit",
            "amount": amount,
            "tool_result": result,
            "tool_status": result.get("status", "credit_issued"),
        }

    if action == "review":
        result = {"status": "manual_review"}
        return {
            "action": "review",
            "amount": 0,
            "tool_result": result,
            "tool_status": result["status"],
        }

    if action == "charge":
        result = {"status": "manual_charge_required"}
        return {
            "action": "charge",
            "amount": amount,
            "tool_result": result,
            "tool_status": result["status"],
        }

    result = {"status": "no_action"}
    return {
        "action": "none",
        "amount": 0,
        "tool_result": result,
        "tool_status": result["status"],
    }


def build_issue_examples(ticket: Dict[str, Any]) -> str:
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")

    if issue_type == "shipping_issue":
        return """
Examples:
- "Hi there, thanks for reaching out — I’ve checked your order and it’s already on the way. You can track it here: [TRACKING LINK]. Estimated delivery: [DATE]. If anything looks off, just reply here and we’ll take care of it."
- "Hi there, I checked the latest shipping status and your package is still moving. Tracking: [TRACKING LINK]. Latest ETA: [DATE]. If you need anything else, reply here and we’ll take care of it."
""".strip()

    if issue_type == "damaged_order":
        return """
Examples:
- "Sorry about that — I’ve flagged the damage case and pushed it into priority handling so the next step gets taken quickly."
- "I’ve reviewed the damage report and moved this into the right recovery flow so it can be resolved properly."
""".strip()

    if issue_type in {"billing_duplicate_charge", "billing_issue", "payment_issue"}:
        return """
Examples:
- "You were charged twice — I’ve flagged the duplicate charge for review and the billing correction is now in motion."
- "I checked the duplicate-charge case and pushed it into the refund path so it can be resolved cleanly."
""".strip()

    return """
Examples:
- "I checked this and I’m already on the next step."
- "I’ve reviewed the case and moved it into the right path from here."
""".strip()


def build_sovereign_prompt(
    message: str,
    ticket: Dict[str, Any],
    user_memory: Dict[str, Any],
    memory_block: str,
    decision: Dict[str, Any],
    learned_action: Dict[str, Any] | None,
    order_info: Dict[str, Any],
    system_prompt: str,
) -> str:
    learned_text = json.dumps(learned_action or {"action": "none", "amount": 0}, ensure_ascii=False)
    decision_text = json.dumps(decision, ensure_ascii=False)
    order_text = json.dumps(order_info, ensure_ascii=False)
    tone_mode = classify_tone(ticket)
    triage = json.dumps(ticket.get("triage", {}), ensure_ascii=False)
    history = json.dumps(ticket.get("customer_history", {}), ensure_ascii=False)
    issue_examples = build_issue_examples(ticket)

    return f"""
{system_prompt}

You are writing as a premium senior support operator.

Style rules:
- Sound human, calm, confident, and useful.
- Lead with the resolution, action, or clearest next step.
- Never sound like a generic chatbot.
- Never expose internal errors, missing fields, IDs, tools, or technical limitations.
- Never say payment_intent_id, charge_id, payload, system prompt, confidence score, or implementation details.
- If something cannot be completed automatically, convert that into a customer-safe next step.
- Avoid filler like "I understand your concern", "please let me know", or "I'm here to assist" unless truly necessary.
- Prefer direct lines like "I checked this", "I’ve already", "This shows as", "I’ve routed this", "Next step:".
- If the customer is frustrated, acknowledge that briefly and then move to the fix.
- If the customer signals cancellation or churn, offer a direct action path and a save path if appropriate.
- No bullet points in the customer-facing message.
- Output JSON only.

Business rules:
- You may only choose one of these actions: none, refund, credit, review, charge.
- Only choose charge when a valid saved Stripe customer and payment method already exist.
- Never invent a refund above ${MAX_REFUND}.
- Never invent a credit above ${MAX_CREDIT}.
- If a hard business decision exists, align to it unless you are escalating risk.
- If risk is high or abuse likelihood is elevated, prefer review over automation.
- For shipping questions, give status and next step, not a generic apology.
- Return internal and customer notes separately.

Tone mode:
{tone_mode}

Customer profile summary:
{user_memory.get("soul_file", "No profile yet.")}

Important memory:
{memory_block}

Current ticket:
- Customer: {ticket.get("customer")}
- Issue type: {ticket.get("issue_type")}
- Sentiment: {ticket.get("sentiment")}/10
- LTV: ${ticket.get("ltv")}
- Operator mode: {ticket.get("operator_mode")}
- User message: {message}

Triage:
{triage}

Customer history:
{history}

Order information:
{order_text}

Hard business decision:
{decision_text}

Learned-rule suggestion:
{learned_text}

Issue-specific examples:
{issue_examples}

Return valid JSON using this exact schema:
{{
  "customer_message": "final message to customer",
  "customer_note": "short customer-facing note",
  "internal_note": "short operator/internal note",
  "action": "none|refund|credit|review|charge",
  "amount": 0,
  "reason": "short internal reason",
  "confidence": 0.0,
  "risk_level": "low|medium|high",
  "priority": "low|medium|high",
  "queue": "new|waiting|escalated|refund_risk|vip|resolved",
  "requires_approval": false
}}
""".strip()


def local_fallback_reply(ticket: Dict[str, Any], planned_action: Dict[str, Any], order_info: Dict[str, Any], message: str) -> Dict[str, Any]:
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    action = str(planned_action.get("action", "none") or "none")
    amount = int(planned_action.get("amount", 0) or 0)
    reason = str(planned_action.get("reason", "") or "")
    triage = ticket.get("triage", {})
    queue = str(planned_action.get("queue", "new") or "new")
    priority = str(planned_action.get("priority", "medium") or "medium")
    risk_level = str(planned_action.get("risk_level", triage.get("risk_level", "medium")) or "medium")

    if issue_type == "shipping_issue":
        status = str(order_info.get("status", ticket.get("order_status", "unknown")) or "unknown")
        tracking = str(order_info.get("tracking", "") or "").strip()
        eta = str(order_info.get("eta", "") or "").strip()
        tracking_line = tracking if tracking else "Tracking link will populate from your order system."
        eta_line = eta if eta else "Delivery date will populate from your order system."

        if status == "processing":
            customer_message = (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked your order and it’s still being processed.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                f"Estimated delivery:\n{eta_line}\n\n"
                "If anything changes or you want me to review the next shipping step, just reply here and we’ll take care of it.\n\n"
                "Best,\nSupport Team"
            )
        elif status == "delivered":
            customer_message = (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked the latest shipping status and the package shows as delivered.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                "If that doesn’t match what you’re seeing, reply here and we’ll investigate the delivery next step.\n\n"
                "Best,\nSupport Team"
            )
        elif status == "delayed":
            customer_message = (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked the latest shipping status and your order appears delayed in transit.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                f"Estimated delivery:\n{eta_line}\n\n"
                "If anything looks off, just reply here and we’ll take care of it.\n\n"
                "Best,\nSupport Team"
            )
        else:
            customer_message = (
                "Hi there,\n\n"
                "Thanks for reaching out — I’ve checked your order and it’s already on the way.\n\n"
                f"You can track it here:\n{tracking_line}\n\n"
                f"Estimated delivery:\n{eta_line}\n\n"
                "If anything looks off, just reply here and we’ll take care of it.\n\n"
                "Best,\nSupport Team"
            )

        if action == "credit" and amount > 0:
            customer_message += f"\n\nI’ve also added a ${amount} credit to help make up for the delay."

        internal_note = f"Shipping case with status={status}, tracking={tracking or 'none'}, eta={eta or 'none'}, triage={triage}."
        return {
            "customer_message": customer_message,
            "customer_note": customer_message,
            "internal_note": internal_note,
            "action": action,
            "amount": amount,
            "reason": reason or "Shipping update provided",
            "confidence": 0.96,
            "risk_level": risk_level,
            "priority": priority,
            "queue": queue or "waiting",
            "requires_approval": bool(planned_action.get("requires_approval", False)),
        }

    if issue_type == "damaged_order":
        if action == "credit" and amount > 0:
            customer_message = f"I’ve reviewed the damage case and applied a ${amount} credit while this gets handled."
        elif action == "review":
            customer_message = "I’ve reviewed the damage case and pushed it into priority handling so it’s resolved correctly."
        else:
            customer_message = "I’ve reviewed the damage case and moved it into the right recovery path so it can be resolved quickly."
        return {
            "customer_message": customer_message,
            "customer_note": customer_message,
            "internal_note": f"Damage flow used. Reason={reason or 'Damaged-order recovery'}.",
            "action": action,
            "amount": amount,
            "reason": reason or "Damaged-order recovery",
            "confidence": 0.95,
            "risk_level": risk_level,
            "priority": "high",
            "queue": queue or "escalated",
            "requires_approval": bool(planned_action.get("requires_approval", False)),
        }

    if action == "refund" and amount > 0:
        customer_message = f"I’ve approved a refund of ${amount} and the correction is now in motion."
    elif action == "credit" and amount > 0:
        customer_message = f"I’ve added a ${amount} credit to help make this right."
    elif action == "charge" and amount > 0:
        customer_message = "I’ve initiated the billing step using your saved payment method and will confirm once it completes."
    elif action == "review":
        customer_message = "I’ve routed this for manual review so the next step is handled safely and correctly."
    else:
        customer_message = "I checked this and I’m already on the next step."

    return {
        "customer_message": customer_message,
        "customer_note": customer_message,
        "internal_note": f"Local fallback path used for {issue_type}. Message={message[:120]}",
        "action": action,
        "amount": amount,
        "reason": reason or "Local fallback",
        "confidence": 0.9,
        "risk_level": risk_level,
        "priority": priority,
        "queue": queue,
        "requires_approval": bool(planned_action.get("requires_approval", False)),
    }


def rewrite_output_for_issue(ticket: Dict[str, Any], executed: Dict[str, Any], parsed: Dict[str, Any], message: str) -> str:
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    text = polish_message(
        safe_output(parsed.get("customer_message", parsed.get("message", "I’ve reviewed this and I’m already on the next step.")))
    )
    lowered = (message or "").strip().lower()

    if "cancel" in lowered:
        return "I can help with that. If you want to cancel, I can move this into the cancellation path now — or, if the issue is the delay or service problem, I can help resolve that first."

    if issue_type in {"billing_duplicate_charge", "billing_issue", "payment_issue"} and executed["action"] == "review":
        return "You were charged twice — I’ve flagged the duplicate charge for review and the billing correction is now in motion."

    if issue_type == "shipping_issue":
        status = str(ticket.get("order_status", "unknown") or "unknown")
        tracking = str(ticket.get("tracking", "") or "").strip()
        eta = str(ticket.get("eta", "") or "").strip()

        tracking_line = tracking if tracking else "Tracking link will populate from your order system."
        eta_line = eta if eta else "Delivery date will populate from your order system."

        if status == "processing":
            return (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked your order and it’s still being processed.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                f"Estimated delivery:\n{eta_line}\n\n"
                "If anything changes or you want me to review the next shipping step, just reply here and we’ll take care of it.\n\n"
                "Best,\nSupport Team"
            )

        if status == "delivered":
            return (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked the latest shipping status and the package shows as delivered.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                "If that doesn’t match what you’re seeing, reply here and we’ll investigate the delivery next step.\n\n"
                "Best,\nSupport Team"
            )

        if status == "delayed":
            return (
                "Hi there,\n\n"
                "Thanks for reaching out — I checked the latest shipping status and your order appears delayed in transit.\n\n"
                f"Tracking:\n{tracking_line}\n\n"
                f"Estimated delivery:\n{eta_line}\n\n"
                "If anything looks off, just reply here and we’ll take care of it.\n\n"
                "Best,\nSupport Team"
            )

        return (
            "Hi there,\n\n"
            "Thanks for reaching out — I’ve checked your order and it’s already on the way.\n\n"
            f"You can track it here:\n{tracking_line}\n\n"
            f"Estimated delivery:\n{eta_line}\n\n"
            "If anything looks off, just reply here and we’ll take care of it.\n\n"
            "Best,\nSupport Team"
        )

    if issue_type == "damaged_order":
        if executed["action"] == "credit" and int(executed.get("amount", 0) or 0) > 0:
            return f"I’ve reviewed the damage case and applied a ${executed['amount']} credit while this gets handled."
        if executed["action"] == "review":
            return "I’ve reviewed the damage case and pushed it into priority handling so it’s resolved correctly."
        return "I’ve reviewed the damage case and moved it into the right recovery path so it can be resolved quickly."

    if executed["action"] == "refund" and f"${executed['amount']}" not in text:
        return f"I’ve approved a refund of ${executed['amount']} and the correction is now in motion."

    if executed["action"] == "credit" and f"${executed['amount']}" not in text:
        return f"I’ve added a ${executed['amount']} credit to help make this right."

    if executed["action"] == "charge" and int(executed.get("amount", 0) or 0) > 0:
        return "I’ve initiated the billing step using your saved payment method and will confirm once it completes."

    if executed["action"] == "review" and "review" not in text.lower():
        return "I’ve routed this for manual review so the next step is handled safely and correctly."

    return text




def _trace(step: str, status: str, detail: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"step": step, "status": status}
    if detail:
        payload["detail"] = detail
    return payload


def _build_memory_delta(history: Dict[str, Any], ticket: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "plan_tier": str(ticket.get("plan_tier", history.get("plan_tier", "free")) or "free"),
        "repeat_customer": bool(history.get("repeat_customer", False)),
        "refund_count": int(history.get("refund_count", 0) or 0),
        "credit_count": int(history.get("credit_count", 0) or 0),
        "review_count": int(history.get("review_count", 0) or 0),
        "complaint_count": int(history.get("complaint_count", 0) or 0),
        "abuse_score": int(history.get("abuse_score", 0) or 0),
        "sentiment_avg": float(history.get("sentiment_avg", 5.0) or 5.0),
        "last_issue_type": str(history.get("last_issue_type", ticket.get("issue_type", "general_support")) or "general_support"),
    }


def _canonicalize_result(
    *,
    customer_message: str,
    ticket: Dict[str, Any],
    triage: Dict[str, Any],
    final_action: Dict[str, Any],
    executed: Dict[str, Any],
    history: Dict[str, Any],
    quality: float,
    mode: str,
    request_context: AgentRequestContext | None,
    internal_note: str,
    customer_note: str,
    thinking_trace: list[dict[str, Any]],
) -> Dict[str, Any]:
    impact = calculate_impact(ticket, final_action)
    tool_status = str(executed.get("tool_status", executed.get("status", "no_action")) or "no_action")
    queue = str(final_action.get("queue", "new") or "new")
    if tool_status in {"pending_approval", "manual_review"}:
        status = "waiting"
    elif queue == "resolved":
        status = "resolved"
    elif str(final_action.get("action", "none") or "none") in {"refund", "credit", "none"}:
        status = "resolved"
    else:
        status = "escalated"

    decision = {
        "action": str(executed.get("action", final_action.get("action", "none")) or "none"),
        "amount": float(executed.get("amount", final_action.get("amount", 0)) or 0),
        "confidence": clamp_confidence(final_action.get("confidence", 0.9), 0.9),
        "reason": str(final_action.get("reason", "") or ""),
        "priority": str(final_action.get("priority", "medium") or "medium"),
        "queue": queue,
        "status": status,
        "risk_level": str(final_action.get("risk_level", triage.get("risk_level", "medium")) or "medium"),
        "requires_approval": bool(final_action.get("requires_approval", False)),
        "tool_status": tool_status,
    }

    impact_projection = {
        "type": str(impact.get("type", "saved") or "saved"),
        "amount": float(impact.get("amount", 0) or 0),
        "money_saved": float(impact.get("money_saved", 0) or 0),
        "auto_resolved": bool(impact.get("auto_resolved", decision["action"] in {"refund", "credit", "none"})),
        "agent_minutes_saved": int(impact.get("agent_minutes_saved", 6 if decision["action"] != "review" else 0) or 0),
        "signals": list(impact.get("signals", [])) if isinstance(impact.get("signals", []), list) else [],
    }

    safe_message = normalize_text(customer_message)

    canonical = {
        "reply": safe_message,
        "final": safe_message,
        "response": safe_message,
        "issue_type": str(ticket.get("issue_type", "general_support") or "general_support"),
        "mode": mode,
        "quality": round(float(quality or 0), 2),
        "triage_metadata": triage,
        "sovereign_decision": decision,
        "impact_projections": impact_projection,
        "memory_delta": _build_memory_delta(history, ticket),
        "thinking_trace": thinking_trace,
        "request_context": request_context.model_dump() if request_context else None,
        "output": {
            "internal_note": normalize_text(internal_note),
            "customer_note": normalize_text(customer_note),
            "audit_log": f"{ticket.get('issue_type', 'general_support')} -> {decision['action']} (${decision['amount']}) | {decision['reason']}",
        },
        # legacy aliases for workspace compatibility
        "action": decision["action"],
        "amount": decision["amount"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "decision": decision,
        "impact": impact_projection,
        "triage": triage,
        "history": _build_memory_delta(history, ticket),
        "order_status": str(ticket.get("order_status", "unknown") or "unknown"),
        "tool_status": decision["tool_status"],
        "tool_result": executed.get("tool_result", {"status": decision["tool_status"]}),
        "meta": {
            "issue_type": str(ticket.get("issue_type", "general_support") or "general_support"),
            "priority": decision["priority"],
            "ltv": int(ticket.get("ltv", 0) or 0),
            "sentiment": int(ticket.get("sentiment", 5) or 5),
            "plan_tier": str(ticket.get("plan_tier", "free") or "free"),
            "operator_mode": str(ticket.get("operator_mode", "balanced") or "balanced"),
            "queue": decision["queue"],
        },
    }
    validated = CanonicalAgentResponse.model_validate(canonical).model_dump()
    validated.update({k: v for k, v in canonical.items() if k not in validated})
    return validated


def run_agent(
    message: str,
    user_id: str = "default-user",
    meta: Dict[str, Any] | None = None,
    request_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    thinking_trace: list[dict[str, Any]] = []
    clean, blocked_reason = sanitize_input(message)
    ctx = AgentRequestContext.model_validate(request_context or {"surface": "workspace"})

    if blocked_reason:
        thinking_trace.append(_trace("sanitize_input", "error", "blocked_input"))
        payload = CanonicalAgentResponse(
            reply=blocked_reason,
            final=blocked_reason,
            response=blocked_reason,
            issue_type="blocked",
            mode="blocked",
            quality=0.0,
            triage_metadata=TriageMetadata(urgency=90, abuse_likelihood=90, complexity=80, recommended_owner="senior_operator", risk_level="high"),
            sovereign_decision=SovereignDecision(action="none", amount=0, confidence=1.0, reason="blocked_input", priority="high", queue="escalated", status="blocked", risk_level="high", requires_approval=False, tool_status="blocked"),
            impact_projections=ImpactProjections(),
            memory_delta=MemoryDelta(),
            thinking_trace=[ThinkingTraceStep(step="sanitize_input", status="error", detail="blocked_input")],
            request_context=ctx,
            output=OutputEnvelope(internal_note="Security layer blocked unsafe input.", customer_note=blocked_reason, audit_log="blocked_input"),
        ).model_dump()
        payload.update({
            "action": "none",
            "amount": 0,
            "confidence": 1.0,
            "reason": "blocked_input",
            "decision": payload["sovereign_decision"],
            "impact": payload["impact_projections"],
            "triage": payload["triage_metadata"],
            "history": payload["memory_delta"],
            "order_status": "blocked",
            "tool_status": "blocked",
            "tool_result": {"status": "blocked"},
            "meta": {"issue_type": "blocked", "priority": "high", "ltv": 0, "sentiment": 5, "plan_tier": "free", "operator_mode": "balanced", "queue": "escalated"},
        })
        return payload

    thinking_trace.append(_trace("sanitize_input", "done"))
    clean = clean or ""

    if is_conversational_message(clean):
        thinking_trace.append(_trace("conversation_gate", "done"))
        return conversational_reply(clean)

    meta = meta or {}
    user_memory = get_user_memory(user_id)
    meta["customer_history"] = user_memory
    ticket = build_ticket(clean, user_id=user_id, meta=meta)
    ticket["request_context"] = ctx.model_dump()
    thinking_trace.append(_trace("build_ticket", "done"))

    order_info: Dict[str, Any] = {}
    if should_attach_order_context(str(ticket.get("issue_type", "general_support"))):
        order_info = get_order(ticket["customer"], clean)
        if ticket.get("order_status") == "unknown":
            ticket["order_status"] = order_info.get("status", "unknown")
        if order_info:
            ticket["tracking"] = order_info.get("tracking", "") or ""
            ticket["eta"] = order_info.get("eta", "") or ""
    else:
        ticket["order_status"] = ticket.get("order_status", "unknown")
    thinking_trace.append(_trace("order_context", "done"))

    triage = ticket.get("triage") or triage_ticket(ticket, user_memory)
    ticket["triage"] = triage
    thinking_trace.append(_trace("triage", "done"))

    brain = load_brain()
    update_system_prompt(brain)
    save_brain(brain)
    memory_block = get_prompt_memory(user_id, limit=5)
    thinking_trace.append(_trace("memory_load", "done"))

    hard_decision = normalize_action_payload(system_decision(ticket))
    thinking_trace.append(_trace("system_decision", "done"))
    learned_action = None
    top_rules = get_top_rule_objects(brain, 5)
    if hard_decision.get("action") == "none":
        learned_action = normalize_action_payload(apply_learned_rules(ticket, top_rules)) if top_rules else None
    thinking_trace.append(_trace("learned_rules", "done"))

    if learned_action and hard_decision.get("action") != "none" and learned_action.get("action") != hard_decision.get("action"):
        thinking_trace.append(_trace("conflict_gate", "error", "learned_rule_conflicts_with_hard_decision"))
        learned_action = None

    planned_action = hard_decision if hard_decision.get("action") != "none" else (learned_action or hard_decision)

    prompt = build_sovereign_prompt(
        message=clean,
        ticket=ticket,
        user_memory=user_memory,
        memory_block=memory_block,
        decision=hard_decision,
        learned_action=learned_action,
        order_info=order_info,
        system_prompt=brain.get("system_prompt", "You are Xalvion."),
    )

    parsed = None
    mode = "sovereign-local"
    confidence = 0.9
    quality = 0.94

    if client is not None:
        try:
            model = choose_model(clean)
            completion = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": brain.get("system_prompt", "You are Xalvion.")},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = completion.choices[0].message.content or ""
            parsed = parse_llm_json(raw)
            mode = f"sovereign-{model}"
            confidence = clamp_confidence(parsed.get("confidence", 0.92), 0.92)
            quality = 0.97
            thinking_trace.append(_trace("llm_response", "done", model))
        except Exception:
            parsed = None
            thinking_trace.append(_trace("llm_response", "error", "provider_failure"))

    if parsed is None:
        parsed = local_fallback_reply(ticket, planned_action, order_info, clean)
        thinking_trace.append(_trace("local_fallback_reply", "done"))

    llm_payload = normalize_action_payload(parsed)

    if hard_decision.get("action") != "none":
        final_action = {**hard_decision, "confidence": confidence}
    elif learned_action and llm_payload.get("action") == "none":
        final_action = {**learned_action, "confidence": confidence}
    else:
        final_action = {
            "action": llm_payload["action"],
            "amount": llm_payload["amount"],
            "reason": str(parsed.get("reason", llm_payload.get("reason", "")) or ""),
            "priority": str(parsed.get("priority", llm_payload.get("priority", "medium")) or "medium"),
            "risk_level": str(parsed.get("risk_level", llm_payload.get("risk_level", triage.get("risk_level", "medium"))) or "medium"),
            "queue": str(parsed.get("queue", llm_payload.get("queue", "new")) or "new"),
            "requires_approval": bool(parsed.get("requires_approval", llm_payload.get("requires_approval", False))),
            "confidence": confidence,
        }

    executed = execute_action(ticket, final_action)
    thinking_trace.append(_trace("execute_action", "done", str(executed.get("tool_status", "no_action"))))

    customer_note = normalize_text(
        polish_message(str(parsed.get("customer_note", parsed.get("customer_message", "")) or ""))
    )
    internal_note = normalize_text(
        str(parsed.get("internal_note", f"Decision path: {final_action.get('reason', 'No reason')}.") or "").strip()
    )
    customer_message = normalize_text(
        rewrite_output_for_issue(ticket, executed, parsed, clean)
    )

    final_payload = {
        **final_action,
        "action": executed.get("action", final_action.get("action", "none")),
        "amount": int(executed.get("amount", final_action.get("amount", 0)) or 0),
        "confidence": confidence,
    }

    update_memory(user_id, ticket, customer_message, final_payload)
    process_feedback(clean, customer_message, quality)
    log_event(clean, customer_message, confidence, quality)
    if quality > 0.92:
        brain_growth = load_brain()
        add_rule(brain_growth, "Maintain strong clarity and confident tone.")
        save_brain(brain_growth)
    thinking_trace.append(_trace("memory_update", "done"))
    thinking_trace.append(_trace("learning_update", "done"))

    refreshed_memory = get_user_memory(user_id)
    return _canonicalize_result(
        customer_message=customer_message,
        ticket=ticket,
        triage=triage,
        final_action=final_payload,
        executed=executed,
        history=refreshed_memory,
        quality=quality,
        mode=mode,
        request_context=ctx,
        internal_note=internal_note,
        customer_note=customer_note or customer_message,
        thinking_trace=thinking_trace,
    )
