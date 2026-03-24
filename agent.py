from __future__ import annotations

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from actions import build_ticket, calculate_impact, apply_learned_rules, system_decision
from brain import add_rule, decay_rules, get_top_rule_objects, load_brain, save_brain, update_system_prompt
from memory import get_prompt_memory, get_user_memory, update_memory
from router import route_task
from security import safe_output, sanitize_input
from tools import get_order, issue_credit, process_refund

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

ALLOWED_ACTIONS = {"none", "refund", "credit", "review"}
MAX_REFUND = 50
MAX_CREDIT = 30


def choose_model(message: str) -> str:
    tier = route_task(message)
    return MODEL_CHEAP if tier == "cheap" else MODEL_EXPENSIVE


def classify_tone(ticket: Dict[str, Any]) -> str:
    sentiment = int(ticket.get("sentiment", 5))
    issue_type = str(ticket.get("issue_type", "general_support"))

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
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return {
        "message": text or "I’ve reviewed this and I’m already on the next step.",
        "action": "none",
        "amount": 0,
        "reason": "fallback_parse",
        "confidence": 0.45,
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
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "  " in text:
        text = text.replace("  ", " ")

    return text.strip()


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
        "hi",
        "hello",
        "hey",
        "heya",
        "yo",
        "sup",
        "wassup",
        "what's up",
        "whats up",
        "how are you",
        "how r u",
        "how are u",
        "who are you",
        "who are u",
        "thanks",
        "thank you",
        "thx",
        "cool",
        "nice",
    }

    if text in conversational_exact:
        return True

    conversational_starts = (
        "hi ",
        "hello ",
        "hey ",
        "yo ",
        "how are you",
        "how are u",
        "what's up",
        "whats up",
        "who are you",
        "who are u",
        "thanks ",
        "thank you ",
    )

    support_markers = (
        "order",
        "package",
        "refund",
        "charged",
        "billing",
        "damaged",
        "late",
        "tracking",
        "delivered",
        "not working",
        "error",
        "invoice",
        "login",
        "password",
        "export",
    )

    if any(marker in text for marker in support_markers):
        return False

    return text.startswith(conversational_starts) or len(text.split()) <= 4


def conversational_reply(message: str) -> Dict[str, Any]:
    text = (message or "").strip().lower()

    if "how are you" in text or "how are u" in text:
        reply = "I’m good — online, focused, and ready to help. Drop the issue and I’ll work it through."
    elif text in {"hi", "hello", "hey", "heya", "yo", "sup", "wassup", "what's up", "whats up"} or text.startswith(
        ("hi ", "hello ", "hey ", "yo ")
    ):
        reply = "Hey — I’m here and ready. Send me the issue and I’ll handle it."
    elif "who are you" in text or "who are u" in text:
        reply = "I’m Xalvion — a support operator built to analyze issues, take the right action, and keep the response clear."
    elif "thanks" in text or "thank you" in text or "thx" in text:
        reply = "Any time."
    else:
        reply = "I’m here and ready. Send me the issue and I’ll handle it."

    return {
        "response": reply,
        "final": reply,
        "mode": "sovereign-conversation",
        "quality": 0.95,
        "confidence": 0.96,
        "action": "none",
        "amount": 0,
        "reason": "conversational_bypass",
        "issue_type": "conversation",
        "order_status": "unknown",
        "tool_result": {"status": "no_action"},
        "tool_status": "no_action",
        "impact": {"type": "saved", "amount": 0},
    }


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
    else:
        amount = 0

    return {
        "action": action,
        "amount": amount,
        "reason": str(payload.get("reason", "") or ""),
    }


def execute_action(ticket: Dict[str, Any], action_payload: Dict[str, Any]) -> Dict[str, Any]:
    safe_action = normalize_action_payload(action_payload)
    action = safe_action["action"]
    amount = safe_action["amount"]
    customer = ticket.get("customer", "Unknown")

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

    result = {"status": "no_action"}
    return {
        "action": "none",
        "amount": 0,
        "tool_result": result,
        "tool_status": result["status"],
    }


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

    return f"""
{system_prompt}

You are writing as a premium senior support operator.

Style rules:
- Sound human, calm, confident, and useful.
- Be concise but not cold.
- Lead with the answer, not filler.
- Never sound like a generic chatbot.
- Never say "I understand your concern" or "please let me know" unless absolutely necessary.
- Prefer "Here’s what I found", "I’ve checked this", "This shows as", "I’ve already", "Next step:".
- If status is available, state it clearly.
- If action is taken, state it clearly.
- If something is missing, ask for the exact missing item in one sentence.
- Avoid weak phrases like "currently unknown" unless there is truly no context at all.
- No bullet points in the customer-facing message.
- Output JSON only.

Business rules:
- You may only choose one of these actions: none, refund, credit, review.
- Never invent a refund above ${MAX_REFUND}.
- Never invent a credit above ${MAX_CREDIT}.
- If a hard business decision exists, align to it.
- If the case is damaged and not auto-approved, move into review.
- For shipping questions, give status and next step, not a generic apology.

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
- User message: {message}

Order information:
{order_text}

Hard business decision:
{decision_text}

Learned-rule suggestion:
{learned_text}

Return valid JSON using this exact schema:
{{
  "message": "final message to customer",
  "action": "none|refund|credit|review",
  "amount": 0,
  "reason": "short internal reason",
  "confidence": 0.0
}}
""".strip()


def shipping_intent_flags(customer_text: str) -> Dict[str, bool]:
    text = (customer_text or "").lower()
    return {
        "asks_where": any(
            p in text
            for p in [
                "where is my order",
                "where's my order",
                "wheres my order",
                "where is my package",
                "where's my package",
                "wheres my package",
            ]
        ),
        "says_delivered_not_received": any(
            p in text
            for p in [
                "delivered but i never got it",
                "delivered but i didnt get it",
                "delivered but i didn't get it",
                "says delivered but i never got it",
                "says delivered but i didnt get it",
                "says delivered but i didn't get it",
                "not received",
                "never got it",
                "hasn't arrived",
                "hasnt arrived",
                "missing package",
                "missing parcel",
            ]
        ),
        "says_late": any(
            p in text
            for p in [
                "late",
                "delayed",
                "still not here",
                "taking too long",
                "where is it",
                "annoyed",
            ]
        ),
    }


def deterministic_shipping_reply(customer_text: str, order_info: Dict[str, Any]) -> str:
    flags = shipping_intent_flags(customer_text)
    status = str(order_info.get("status", "unknown")).lower()
    tracking = str(order_info.get("tracking", "")).strip()
    eta = str(order_info.get("eta", "")).strip()

    tracking_part = f" The tracking reference is {tracking}." if tracking else ""
    eta_part = f" The latest estimate is {eta}." if eta and eta.lower() != status else ""

    if flags["says_delivered_not_received"]:
        if tracking:
            return (
                f"Your package shows as delivered under tracking reference {tracking}. "
                "Since you haven’t received it, I’d treat this as a delivery investigation. "
                "Send the order email or number and I’ll help move it through the next step."
            )
        return (
            "Your package shows as delivered. Since you haven’t received it, I’d treat this as a delivery investigation. "
            "Send the order email or number and I’ll help move it through the next step."
        )

    if flags["says_late"]:
        if status == "delayed":
            return (
                f"Your order appears delayed in transit.{tracking_part}{eta_part} "
                "Send the order email or number and I’ll help work from the latest shipping status."
            ).strip()

        if status == "processing":
            return (
                f"Your order is still processing and has not left yet.{tracking_part} "
                "Send the order email or number and I can help check the next shipping step."
            ).strip()

    if flags["asks_where"]:
        if status == "processing":
            return (
                f"Your order is still processing and has not left yet.{tracking_part} "
                "If you send the order email or number, I can help check the next shipping step."
            ).strip()

        if status == "shipped":
            return (
                f"Your package has already shipped.{tracking_part}{eta_part} "
                "If you want, send the order email or number and I’ll help narrow down the latest step."
            ).strip()

        if status == "delayed":
            return (
                f"Your order appears delayed in transit.{tracking_part}{eta_part} "
                "Send the order email or number and I’ll help work from the latest shipping status."
            ).strip()

        if status == "delivered":
            return (
                f"Your package shows as delivered.{tracking_part} "
                "If that doesn’t match what you’re seeing, send the order email or order number and I’ll help investigate the next step."
            ).strip()

    if status == "processing":
        return (
            f"Your order is still processing and has not left yet.{tracking_part} "
            "Send the order email or order number and I can help check the next shipping step."
        ).strip()

    if status == "shipped":
        return (
            f"Your package has already shipped.{tracking_part}{eta_part} "
            "Send the order email or order number and I’ll help narrow down the latest step."
        ).strip()

    if status == "delayed":
        return (
            f"Your order appears delayed in transit.{tracking_part}{eta_part} "
            "Send the order email or order number and I’ll help work from the latest shipping status."
        ).strip()

    if status == "delivered":
        return (
            f"Your package shows as delivered.{tracking_part} "
            "If that doesn’t match what you’re seeing, send the order email or order number and I’ll help investigate the next step."
        ).strip()

    return "I can help check that. Send the order email or order number and I’ll narrow down the next step."


def local_billing_message(final_action: Dict[str, Any]) -> str:
    action = final_action.get("action", "none")
    amount = int(final_action.get("amount", 0) or 0)

    if action == "refund":
        return f"I’ve approved a refund of ${amount} for the duplicate charge and the correction is now in motion."

    if action == "review":
        return "I’ve flagged the billing issue for review and the next step is already underway."

    return "I’ve reviewed the billing issue and I’m already moving it through the correct next step."


def local_damaged_message(final_action: Dict[str, Any]) -> str:
    action = final_action.get("action", "none")
    amount = int(final_action.get("amount", 0) or 0)

    if action == "credit":
        return (
            f"I’ve added a ${amount} credit to help make this right. "
            "Send the order number and one photo of the damage and I’ll move the case through the next step."
        )

    if action == "review":
        return (
            "I’ve opened this for manual review so it moves properly. "
            "Send the order number and one photo of the damage and I’ll tighten up the next step."
        )

    return (
        "I’m sorry this arrived damaged. Send the order number and one photo of the damage "
        "and I’ll move it toward a fix right away."
    )


def local_refund_message(final_action: Dict[str, Any]) -> str:
    action = final_action.get("action", "none")
    amount = int(final_action.get("amount", 0) or 0)

    if action == "refund":
        return f"I’ve approved a refund of ${amount} and the correction is now underway."

    if action == "review":
        return "I’ve flagged the refund request for review. Send the order number or order email and I’ll tighten up the next step."

    return "I’ve reviewed the refund request and the next step depends on the order details, so send the order number or order email."


def local_fallback_reply(
    ticket: Dict[str, Any],
    final_action: Dict[str, Any],
    order_info: Dict[str, Any],
    customer_text: str,
) -> Dict[str, Any]:
    issue_type = ticket.get("issue_type", "general_support")
    action = final_action.get("action", "none")
    amount = int(final_action.get("amount", 0) or 0)

    if issue_type == "shipping_issue":
        msg = deterministic_shipping_reply(customer_text, order_info)
    elif issue_type == "billing_duplicate_charge":
        msg = local_billing_message(final_action)
    elif issue_type == "damaged_order":
        msg = local_damaged_message(final_action)
    elif issue_type == "refund_request":
        msg = local_refund_message(final_action)
    elif action == "refund":
        msg = f"I’ve approved a refund of ${amount} and the correction is already in motion."
    elif action == "credit":
        msg = f"I’ve added a ${amount} credit to help make this right, and I’m continuing with the next step."
    elif action == "review":
        msg = "I’ve flagged this for review and the next step is already underway."
    else:
        msg = "I’ve reviewed this and I’m already on the next appropriate step."

    return {
        "message": msg,
        "action": action,
        "amount": amount,
        "reason": "local_fallback",
        "confidence": 0.9,
    }


def maybe_learn(brain: Dict[str, Any], ticket: Dict[str, Any], quality: float) -> None:
    issue_type = ticket.get("issue_type")
    sentiment = int(ticket.get("sentiment", 5))

    if quality < 0.5 and issue_type == "shipping_issue":
        add_rule(
            brain,
            {
                "trigger": "shipping_low_quality_fix",
                "condition": {"issue_type": "shipping_issue", "sentiment_lte": 5},
                "action": {"type": "credit", "amount": 10},
            },
        )

    if sentiment <= 2:
        add_rule(
            brain,
            {
                "trigger": "very_negative_empathy_credit",
                "condition": {"sentiment_lte": 2},
                "action": {"type": "credit", "amount": 15},
            },
        )


def run_agent(message: str, user_id: str = "default-user", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    clean, blocked_reason = sanitize_input(message)
    if blocked_reason:
        return {
            "response": blocked_reason,
            "final": blocked_reason,
            "mode": "blocked",
            "quality": 0.0,
            "confidence": 1.0,
            "action": "none",
            "amount": 0,
            "reason": "blocked_input",
            "issue_type": "blocked",
            "order_status": "blocked",
            "tool_result": {"status": "blocked"},
            "tool_status": "blocked",
            "impact": {"type": "saved", "amount": 0},
        }

    clean = clean or ""
    if is_conversational_message(clean):
        return conversational_reply(clean)

    meta = meta or {}
    ticket = build_ticket(clean, user_id=user_id, meta=meta)

    order_info = {}
    if should_attach_order_context(str(ticket.get("issue_type", "general_support"))):
        order_info = get_order(ticket["customer"], clean)
        if ticket.get("order_status") == "unknown":
            ticket["order_status"] = order_info.get("status", "unknown")
    else:
        ticket["order_status"] = "unknown"

    brain = load_brain()
    update_system_prompt(brain)
    save_brain(brain)

    user_memory = get_user_memory(user_id)
    memory_block = get_prompt_memory(user_id, limit=5)

    hard_decision = normalize_action_payload(system_decision(ticket))

    if ticket.get("issue_type") == "damaged_order" and hard_decision.get("action") == "none":
        hard_decision = {
            "action": "review",
            "amount": 0,
            "reason": "Damaged-order escalation path",
        }

    learned_action = None
    if hard_decision.get("action") == "none":
        learned_action = normalize_action_payload(apply_learned_rules(ticket, get_top_rule_objects(brain, 5)))

    planned_action = hard_decision if hard_decision.get("action") != "none" else (learned_action or hard_decision)

    if ticket.get("issue_type") == "shipping_issue":
        parsed = local_fallback_reply(ticket, planned_action, order_info, clean)
        mode = "sovereign-shipping-locked"
        confidence = 0.96
        quality = 0.98
    elif ticket.get("issue_type") == "damaged_order":
        parsed = local_fallback_reply(ticket, planned_action, order_info, clean)
        mode = "sovereign-damage-locked"
        confidence = 0.95
        quality = 0.97
    else:
        prompt = build_sovereign_prompt(
            message=clean,
            ticket=ticket,
            user_memory=user_memory,
            memory_block=memory_block,
            decision=hard_decision,
            learned_action=learned_action,
            order_info=order_info,
            system_prompt=brain["system_prompt"],
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
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": brain["system_prompt"]},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = completion.choices[0].message.content or ""
                parsed = parse_llm_json(raw)
                mode = f"sovereign-{model}"
                confidence = clamp_confidence(parsed.get("confidence", 0.92), 0.92)
                quality = 0.97
            except Exception:
                parsed = None

        if parsed is None:
            parsed = local_fallback_reply(ticket, planned_action, order_info, clean)

    normalized_llm = normalize_action_payload(parsed)
    llm_action = normalized_llm["action"]
    llm_amount = normalized_llm["amount"]

    if hard_decision.get("action") != "none":
        final_action = hard_decision
    elif learned_action and llm_action == "none":
        final_action = learned_action
    else:
        final_action = {
            "action": llm_action,
            "amount": llm_amount,
            "reason": normalized_llm.get("reason", ""),
        }

    executed = execute_action(ticket, final_action)

    customer_message = polish_message(
        safe_output(parsed.get("message", "I’ve reviewed this and I’m already on the next step."))
    )

    if executed["action"] == "refund" and f"${executed['amount']}" not in customer_message:
        customer_message = f"I’ve approved a refund of ${executed['amount']} and the correction is now in motion."
    elif executed["action"] == "credit" and f"${executed['amount']}" not in customer_message:
        customer_message = (
            f"I’ve added a ${executed['amount']} credit to help make this right, "
            "and I’m continuing with the next step."
        )
    elif executed["action"] == "review":
        if ticket.get("issue_type") == "damaged_order":
            customer_message = (
                "I’ve opened this for manual review so it moves properly. "
                "Send the order number and one photo of the damage and I’ll tighten up the next step."
            )
        else:
            customer_message = "I’ve flagged this for review and the next step is already underway."

    update_memory(user_id, ticket, customer_message)

    maybe_learn(brain, ticket, quality)
    decay_rules(brain)
    save_brain(brain)

    process_feedback(clean, customer_message, quality)
    log_event(clean, customer_message, confidence, quality)

    impact = calculate_impact(ticket, executed)

    return {
        "response": customer_message,
        "final": customer_message,
        "mode": mode,
        "quality": round(quality, 2),
        "confidence": clamp_confidence(confidence, 0.9),
        "action": executed["action"],
        "amount": executed["amount"],
        "reason": parsed.get("reason", final_action.get("reason", "resolved")),
        "issue_type": ticket.get("issue_type", "general_support"),
        "order_status": ticket.get("order_status", "unknown"),
        "tool_result": executed.get("tool_result", {}),
        "tool_status": executed.get("tool_status", "unknown"),
        "impact": impact,
    }