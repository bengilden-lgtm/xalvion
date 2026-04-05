from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from actions import (
    MAX_APPROVAL_THRESHOLD,
    MAX_AUTO_CREDIT_AMOUNT,
    MAX_AUTO_REFUND_AMOUNT,
    HANDLED_ISSUE_TYPES,
    apply_learned_rules,
    build_ticket,
    compute_execution_tier,
    execute_action as dispatch_integrated_action,
    merge_impact_with_business_projection,
    system_decision,
    triage_ticket,
)
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

try:
    from learning import learn_from_ticket
except Exception:
    def learn_from_ticket(ticket, decision, outcome, outcome_key=None):
        return None

try:
    from outcome_store import log_outcome as _log_outcome
except Exception:
    def _log_outcome(outcome_key, user_id, action, amount, issue_type, tool_result, auto_resolved=True, approved_by_human=False):
        return {}


load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4o-mini")
MODEL_EXPENSIVE = os.getenv("MODEL_EXPENSIVE", "gpt-4o-mini")

client = OpenAI(api_key=API_KEY, timeout=14.0) if API_KEY else None

ALLOWED_ACTIONS = {"none", "refund", "credit", "review", "charge"}
MAX_REFUND = int(MAX_AUTO_REFUND_AMOUNT)
MAX_CREDIT = int(MAX_AUTO_CREDIT_AMOUNT)


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
    queue = str(action_payload.get("queue", "new") or "new")
    priority = str(action_payload.get("priority", "medium") or "medium")
    risk_level = str(action_payload.get("risk_level", triage.get("risk_level", "medium")) or "medium")

    conf_val = float(clamp_confidence(confidence, 0.9))
    impact = merge_impact_with_business_projection(ticket, safe_action, confidence=conf_val)
    final_like = {
        "action": safe_action["action"],
        "amount": safe_action["amount"],
        "reason": str(action_payload.get("reason", "") or ""),
        "priority": priority,
        "queue": queue,
        "risk_level": risk_level,
        "requires_approval": bool(action_payload.get("requires_approval", False)),
        "confidence": conf_val,
    }
    executed_like = {
        "action": safe_action["action"],
        "amount": safe_action["amount"],
        "tool_status": tool_payload.get("tool_status", "no_action"),
        "tool_result": tool_payload.get("tool_result", {"status": "no_action"}),
    }
    impact_projection = {
        "type": str(impact.get("type", "saved") or "saved"),
        "amount": float(impact.get("amount", 0) or 0),
        "money_saved": float(impact.get("money_saved", 0) or 0),
        "agent_minutes_saved": int(impact.get("agent_minutes_saved", 0) or 0),
        "auto_resolved": bool(impact.get("auto_resolved", False)),
        "revenue_at_risk": float(impact.get("revenue_at_risk", 0) or 0),
        "revenue_saved": float(impact.get("revenue_saved", 0) or 0),
        "churn_risk_delta": float(impact.get("churn_risk_delta", 0) or 0),
        "refund_cost": float(impact.get("refund_cost", 0) or 0),
        "time_saved": float(impact.get("time_saved", 0) or 0),
        "confidence_band": dict(impact.get("confidence_band") or {}),
    }
    decision_explanation = build_decision_explanation(
        ticket=ticket,
        triage=triage,
        hard_decision=final_like,
        learned_action=None,
        final_action=final_like,
        executed=executed_like,
        history=history,
        brain_rules=[],
        confidence=conf_val,
        quality=float(quality or 0),
        impact_projection=impact_projection,
    )
    try:
        from actions import compute_execution_tier as _cet

        execution_tier = _cet(
            str(final_like["action"]),
            float(final_like.get("amount", 0) or 0),
            conf_val,
            float(quality or 0),
            str(final_like.get("risk_level", "medium") or "medium"),
            int(history.get("abuse_score", 0) or 0),
            int(history.get("refund_count", 0) or 0),
            str(ticket.get("operator_mode", "balanced") or "balanced"),
            bool(final_like.get("requires_approval", False)),
        )
    except Exception:
        execution_tier = "approval_required"
    decision_explanation["execution_tier"] = execution_tier

    try:
        from learning import get_pattern_expectation as _gpat

        pat = _gpat({**ticket, "triage": triage}, final_like)
    except Exception:
        pat = None

    try:
        decision_explainability = build_decision_explainability(
            ticket=ticket,
            triage=triage,
            hard_decision=final_like,
            learned_action=None,
            final_action=final_like,
            executed=executed_like,
            history=history,
            top_rules=[],
            confidence=conf_val,
            quality=float(quality or 0),
            pattern_expectation=pat,
        )
    except Exception:
        decision_explainability = None

    return {
        "response": customer_message,
        "final": customer_message,
        "reply": customer_message,
        "mode": mode,
        "quality": round(float(quality or 0), 2),
        "confidence": conf_val,
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
            "confidence": conf_val,
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
        "decision_explanation": decision_explanation,
        "decision_explainability": decision_explainability,
        "execution_tier": execution_tier,
        "outcome_key": None,
        "audit_summary": build_audit_summary_payload(
            proposed_action=final_like,
            executed=executed_like,
            outcome_key=None,
            human_approved=False,
            issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        ),
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
    return issue_type in HANDLED_ISSUE_TYPES and issue_type in {"shipping_issue", "damaged_order"}


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

    if safe_action.get("requires_approval"):
        result = {"status": "pending_approval", "type": "approval_gate", "message": "Action held for approval"}
        return {"action": "review", "amount": 0, "tool_result": result, "tool_status": result["status"]}

    request_context = ticket.get("request_context") or {}
    customer_email = str(ticket.get("customer_email") or request_context.get("sender") or "").strip()
    if customer_email and "@" not in customer_email:
        customer_email = ""

    payload: Dict[str, Any] = {
        "customer": ticket.get("customer", "Unknown"),
        "customer_name": ticket.get("customer", "there"),
        "customer_email": customer_email,
        "message": str(ticket.get("issue", "") or ""),
        "issue_type": str(ticket.get("issue_type", "general_support") or "general_support"),
        "source": str(ticket.get("source", "workspace") or "workspace"),
        "priority": str(safe_action.get("priority", "medium") or "medium"),
        "amount": amount,
        "status": str(ticket.get("order_status", "unknown") or "unknown"),
        "order_status": str(ticket.get("order_status", "unknown") or "unknown"),
        "tracking_id": str(ticket.get("tracking", "") or ""),
        "tracking_url": str(ticket.get("tracking_url", "") or ""),
        "eta": str(ticket.get("eta", "") or ""),
        "carrier": str(ticket.get("carrier", "") or ""),
        "order_id": str(ticket.get("order_id", "") or ""),
    }

    if action == "refund":
        result = process_refund(payload["customer"], amount)
        if result.get("error"):
            return {"action": "review", "amount": 0, "tool_result": result, "tool_status": result.get("error", "error")}
        return {"action": "refund", "amount": amount, "tool_result": result, "tool_status": result.get("status", "success")}

    if action == "credit":
        result = issue_credit(payload["customer"], amount)
        return {"action": "credit", "amount": amount, "tool_result": result, "tool_status": result.get("status", "credit_issued")}

    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")

    # Standard shipping / damage — never hit integration dispatch (including charge).
    if issue_type == "shipping_issue":
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_tracking", "type": "tracking", "message": "Shipping handled locally"},
            "tool_status": "local_tracking",
        }

    if issue_type == "damaged_order":
        return {
            "action": "review",
            "amount": 0,
            "tool_result": {"status": "local_damage_flow", "type": "escalation", "message": "Damage routed locally"},
            "tool_status": "local_damage_flow",
        }

    if issue_type in {"billing_duplicate_charge", "billing_issue", "payment_issue"}:
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_billing_flow", "type": "billing", "message": "Billing handled locally"},
            "tool_status": "local_billing_flow",
        }

    if issue_type == "refund_request":
        return {
            "action": "none",
            "amount": 0,
            "tool_result": {"status": "local_refund_request", "type": "billing", "message": "Refund request handled locally"},
            "tool_status": "local_refund_request",
        }

    if action == "charge":
        integration_result = dispatch_integrated_action("charge", payload)
        return {"action": "charge", "amount": amount, "tool_result": integration_result, "tool_status": integration_result.get("status", "manual_charge_required")}

    integrated_action = "escalate" if action == "review" else action
    integration_result = dispatch_integrated_action(integrated_action, payload)
    mapped_action = "review" if integrated_action == "escalate" else action

    return {
        "action": mapped_action,
        "amount": amount if mapped_action in {"refund", "credit", "charge"} else 0,
        "tool_result": integration_result,
        "tool_status": integration_result.get("status", "success"),
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
    def _finalize_local_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        cm = str(payload.get("customer_message") or "").strip()
        conf = float(payload.get("confidence") or 0.9)
        payload["reply"] = payload.get("reply") or cm
        payload["response"] = payload.get("response") or cm
        payload["final"] = payload.get("final") or cm
        if payload.get("quality") is None:
            payload["quality"] = conf
        return payload

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
        return _finalize_local_payload({
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
        })

    if issue_type == "damaged_order":
        if action == "credit" and amount > 0:
            customer_message = f"I’ve reviewed the damage case and applied a ${amount} credit while this gets handled."
        elif action == "review":
            customer_message = "I’ve reviewed the damage case and pushed it into priority handling so it’s resolved correctly."
        else:
            customer_message = "I’ve reviewed the damage case and moved it into the right recovery path so it can be resolved quickly."
        return _finalize_local_payload({
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
        })

    if issue_type == "billing_duplicate_charge":
        customer_message = (
            "You were charged twice — I’ve flagged this for billing correction and duplicate-charge review "
            "so the extra charge is removed or refunded properly. You’ll get a confirmation once it’s resolved."
        )
        return _finalize_local_payload({
            "customer_message": customer_message,
            "customer_note": customer_message,
            "internal_note": "Billing duplicate fast path — customer-safe reply, no automatic execution.",
            "action": "none",
            "amount": 0,
            "reason": reason or "Duplicate charge acknowledgment",
            "confidence": 0.94,
            "risk_level": risk_level,
            "priority": priority,
            "queue": queue or "refund_risk",
            "requires_approval": False,
        })

    if issue_type == "refund_request":
        customer_message = (
            "I’ve received your refund request and I’m reviewing the order details now — "
            "I’ll confirm the next step shortly, including timing and what to expect on your statement."
        )
        return _finalize_local_payload({
            "customer_message": customer_message,
            "customer_note": customer_message,
            "internal_note": "Refund request fast path — customer-safe reply, no automatic execution.",
            "action": "none",
            "amount": 0,
            "reason": reason or "Refund request acknowledgment",
            "confidence": 0.93,
            "risk_level": risk_level,
            "priority": priority,
            "queue": queue or "refund_risk",
            "requires_approval": False,
        })

    if issue_type in {"billing_issue", "payment_issue"}:
        customer_message = (
            "I’ve reviewed your billing concern and I’m on it — I’ll confirm what happened with the charge "
            "and the fastest path to fix it, including any correction or refund if it applies."
        )
        return _finalize_local_payload({
            "customer_message": customer_message,
            "customer_note": customer_message,
            "internal_note": "Billing/payment fast path — customer-safe reply, no automatic execution.",
            "action": "none",
            "amount": 0,
            "reason": reason or "Billing issue acknowledgment",
            "confidence": 0.92,
            "risk_level": risk_level,
            "priority": priority,
            "queue": queue or "waiting",
            "requires_approval": False,
        })

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

    return _finalize_local_payload({
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
    })


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




def compute_quality(
    confidence: float,
    triage: Dict[str, Any],
    executed: Dict[str, Any],
    history: Dict[str, Any],
    llm_used: bool,
) -> float:
    """
    Compute a real quality signal from observable execution factors.
    Replaces the previous hardcoded 0.97 / 0.94 constants.
    """
    score = float(confidence)
    if llm_used:
        score += 0.04
    tool_status = str(executed.get("tool_status", executed.get("status", "")) or "")
    if tool_status in {"success", "credit_issued"}:
        score += 0.04
    elif tool_status in {"error", "pending_review"}:
        score -= 0.06
    action = str(executed.get("action", "none") or "none")
    if action == "review":
        score -= 0.08
    abuse_likelihood = float(triage.get("abuse_likelihood", 0)) / 100.0
    score *= (1.0 - abuse_likelihood * 0.25)
    abuse_score = int(history.get("abuse_score", 0) or 0)
    if abuse_score > 1:
        score -= (abuse_score - 1) * 0.05
    return round(max(0.50, min(0.99, score)), 2)


def _human_issue_label(issue_type: str) -> str:
    raw = str(issue_type or "general_support").replace("_", " ").strip()
    return raw[:1].upper() + raw[1:] if raw else "General support"


def _sanitize_audit_rationale(text: str, max_len: int = 220) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


def _audit_action_label(action: str, amount: float) -> str:
    a = str(action or "none").strip().lower()
    try:
        amt = float(amount or 0)
    except Exception:
        amt = 0.0
    if a == "none":
        return "No billing motion"
    if a in {"refund", "credit", "charge"} and amt > 0:
        return f"{a.replace('_', ' ').title()} ${amt:.0f}"
    if a == "review":
        return "Escalated for review"
    return a.replace("_", " ").title()


def _friendly_execution_status(tool_status: str) -> str:
    s = str(tool_status or "unknown").strip().lower().replace("_", " ")
    mapping = {
        "pending approval": "held for approval",
        "approved pending execution": "approved — execution pending",
        "credit issued": "credit issued",
        "local tracking": "shipping update path",
        "local damage flow": "damage recovery path",
        "local billing flow": "billing review path",
        "local refund request": "refund request path",
        "local fast path": "fast-path response",
        "no action": "no system action",
    }
    return mapping.get(s, s or "completed")


def build_audit_summary_payload(
    *,
    proposed_action: Dict[str, Any],
    executed: Dict[str, Any],
    outcome_key: str | None,
    human_approved: bool,
    issue_type: str,
) -> Dict[str, Any]:
    """
    Compact audit / trust trace for one decision. Safe for UI and external stakeholders:
    no API secrets, raw tool payloads, or customer message bodies.
    """
    prop = proposed_action or {}
    ex = executed or {}
    prop_act = str(prop.get("action", "none") or "none")
    prop_amt = float(prop.get("amount", 0) or 0)
    req_appr = bool(prop.get("requires_approval", False))

    rationale = _sanitize_audit_rationale(str(prop.get("reason", "") or ""))
    if not rationale:
        rationale = f"Classified as {_human_issue_label(issue_type)} with policy-aligned routing."

    exec_act = str(ex.get("action", prop_act) or prop_act)
    exec_amt = float(ex.get("amount", prop_amt) or prop_amt)
    tool_status = str(ex.get("tool_status", ex.get("status", "no_action")) or "no_action")

    approval_required = req_appr or tool_status in {"pending_approval", "manual_review"}
    human_ok = bool(human_approved)

    if approval_required:
        appr_line = (
            "Approval: Required · Operator confirmed in workspace"
            if human_ok
            else "Approval: Required · Awaiting operator confirmation"
        )
    else:
        appr_line = "Approval: Not required for this path"

    prop_label = _audit_action_label(prop_act, prop_amt)
    exec_label = _audit_action_label(exec_act, exec_amt)
    exec_human = _friendly_execution_status(tool_status)

    if tool_status == "pending_approval":
        exec_line = f"Execution: Not run yet — {prop_label} is held until an operator approves."
    else:
        exec_line = f"What ran: {exec_label} — {exec_human}"

    trace = [
        f"Proposed: {prop_label}",
        f"Why: {rationale}",
        appr_line,
        exec_line,
    ]

    return {
        "version": 1,
        "outcome_key": outcome_key,
        "proposed": {
            "action": prop_act,
            "amount": round(prop_amt, 2),
            "label": prop_label,
        },
        "rationale": rationale,
        "approval": {
            "required": approval_required,
            "human_confirmed": human_ok,
        },
        "execution": {
            "action": exec_act,
            "amount": round(exec_amt, 2),
            "status": tool_status,
            "label": exec_label,
        },
        "outcome": {
            "known": False,
            "summary": None,
            "tier": None,
            "success": None,
        },
        "trace": trace,
    }


def build_decision_explainability(
    *,
    ticket: Dict[str, Any],
    triage: Dict[str, Any],
    hard_decision: Dict[str, Any],
    learned_action: Dict[str, Any] | None,
    final_action: Dict[str, Any],
    executed: Dict[str, Any],
    history: Dict[str, Any],
    top_rules: list,
    confidence: float,
    quality: float,
    pattern_expectation: dict | None = None,
) -> dict[str, Any]:
    """Deterministic operator explainability — no LLM."""
    ticket = ticket or {}
    triage = triage or {}
    hard_decision = hard_decision or {}
    final_action = final_action or {}
    history = history or {}
    top_rules = top_rules or []

    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    action = str(final_action.get("action", "none") or "none")
    amount = float(final_action.get("amount", 0) or 0)
    risk_level = str(triage.get("risk_level", "medium") or "medium")
    urgency = int(triage.get("urgency", 0) or 0)
    churn_risk = int(triage.get("churn_risk", 0) or 0)
    abuse_lh = int(triage.get("abuse_likelihood", 0) or 0)
    refund_lh = int(triage.get("refund_likelihood", 0) or 0)
    req_approval = bool(final_action.get("requires_approval", False))
    refund_count = int(history.get("refund_count", 0) or 0)
    abuse_score = int(history.get("abuse_score", 0) or 0)
    repeat = bool(history.get("repeat_customer", False))
    sentiment = float(history.get("sentiment_avg", 5.0) or 5.0)

    classification_signals = {
        "billing_duplicate_charge": "Matched duplicate charge pattern",
        "damaged_order":            "Matched damaged order pattern",
        "shipping_issue":           "Matched shipping inquiry pattern",
        "refund_request":           "Matched explicit refund request",
        "billing_issue":            "Matched billing issue pattern",
        "payment_issue":            "Matched payment issue pattern",
        "auth_issue":               "Matched authentication issue",
        "export_error":             "Matched export/data error",
        "general_support":          "No specific pattern matched",
    }
    classification_signal = classification_signals.get(
        issue_type, "Classified as general support"
    )

    risk_factors: list[str] = []
    if abuse_lh >= 50:
        risk_factors.append("high abuse likelihood")
    if refund_count >= 3:
        risk_factors.append(f"{refund_count} prior refunds")
    if abuse_score >= 2:
        risk_factors.append("elevated abuse score")
    if churn_risk >= 60:
        risk_factors.append("high churn risk")
    if urgency >= 70:
        risk_factors.append("high urgency")
    risk_reasoning = (
        f"{risk_level.title()} risk"
        + (f" — {', '.join(risk_factors)}" if risk_factors else "")
    )

    policy_triggered = str(hard_decision.get("action", "none")) != "none"
    policy_reason = str(hard_decision.get("reason", "") or "")
    policy_signal = (
        f"Policy applied: {policy_reason}" if policy_triggered and policy_reason
        else "No hard policy triggered — learning rules applied"
        if not policy_triggered
        else "Policy triggered"
    )

    memory_parts: list[str] = []
    if repeat:
        memory_parts.append("returning customer")
    if sentiment < 4.0:
        memory_parts.append("historically frustrated")
    elif sentiment > 7.0:
        memory_parts.append("historically positive")
    if refund_count >= 2:
        memory_parts.append(f"{refund_count} refunds on record")
    memory_signal = (
        "Memory: " + ", ".join(memory_parts)
        if memory_parts
        else "No significant memory signals"
    )

    learned_trigger = None
    learned_weight = None
    if learned_action and str(learned_action.get("action", "none")) != "none":
        lat = learned_action.get("action")
        if top_rules:
            matched = next(
                (
                    r for r in top_rules
                    if r.get("action", {}).get("type") == lat
                ),
                None,
            )
            if matched:
                learned_trigger = matched.get("trigger")
                learned_weight = matched.get("weight")

    if pattern_expectation:
        exp_label = pattern_expectation.get("expectation", "medium")
        exp_count = pattern_expectation.get("sample_count", 0)
        outcome_expectation = (
            f"Pattern history: {exp_label} outcomes "
            f"({exp_count} similar decisions observed)"
        )
    else:
        outcome_expectation = "No pattern history available for this decision type"

    alternatives: list[str] = []
    if action != "refund":
        if refund_lh >= 60:
            alternatives.append(
                "Refund was considered but "
                + (
                    "abuse signals blocked it" if abuse_score >= 2
                    else "policy routed to review"
                    if req_approval else "not triggered by current policy"
                )
            )
    if action != "credit" and issue_type in {"shipping_issue", "damaged_order"}:
        alternatives.append(
            "Credit was available but not triggered by current sentiment/policy thresholds"
        )
    if action == "none":
        alternatives.append(
            "No financial action taken — issue type does not meet action thresholds"
        )
    why_not = (
        "; ".join(alternatives)
        if alternatives
        else "Other actions were not applicable to this issue type"
    )

    if req_approval:
        approval_reason = (
            "Abuse score elevated" if abuse_score >= 2
            else f"Refund amount ${amount:.0f} above auto-approval threshold"
            if action == "refund" and amount > 0
            else "Risk level or policy requires operator confirmation"
        )
    else:
        approval_reason = "Within automatic handling thresholds"

    summary_parts = [
        f"{issue_type.replace('_', ' ').title()} detected.",
        f"Risk: {risk_level}.",
    ]
    if policy_triggered:
        summary_parts.append(f"Policy: {policy_reason}.")
    if memory_parts:
        summary_parts.append(f"Customer context: {', '.join(memory_parts)}.")
    summary_parts.append(
        f"Action: {action}"
        + (f" (${amount:.0f})" if amount > 0 else "")
        + (" — requires approval." if req_approval else " — auto-handled.")
    )
    summary = " ".join(summary_parts)

    return {
        "classification": {
            "issue_type": issue_type,
            "signal":     classification_signal,
        },
        "risk_reasoning": {
            "level":            risk_level,
            "urgency":          urgency,
            "churn_risk":       churn_risk,
            "abuse_likelihood": abuse_lh,
            "signal":           risk_reasoning,
        },
        "policy_trigger": {
            "triggered": policy_triggered,
            "reason":    policy_reason,
            "signal":    policy_signal,
        },
        "memory_influence": {
            "repeat_customer": repeat,
            "refund_count":    refund_count,
            "abuse_score":     abuse_score,
            "sentiment_avg":   round(sentiment, 1),
            "signal":          memory_signal,
        },
        "learned_rule_influence": {
            "applied": bool(
                learned_action and str(learned_action.get("action", "none") or "none") != "none"
            ),
            "trigger": learned_trigger,
            "weight":  learned_weight,
        },
        "outcome_expectation": {
            "pattern_key": (
                pattern_expectation.get("pattern_key")
                if pattern_expectation else None
            ),
            "ema_score": (
                pattern_expectation.get("ema_score")
                if pattern_expectation else None
            ),
            "signal": outcome_expectation,
        },
        "why_not_other_actions": why_not,
        "approval_rationale": {
            "required": req_approval,
            "reason":   approval_reason,
        },
        "summary": summary,
    }


def build_decision_explanation(
    *,
    ticket: Dict[str, Any],
    triage: Dict[str, Any],
    hard_decision: Dict[str, Any],
    learned_action: Dict[str, Any] | None,
    final_action: Dict[str, Any],
    executed: Dict[str, Any],
    history: Dict[str, Any],
    brain_rules: list[Dict[str, Any]],
    confidence: float,
    quality: float,
    impact_projection: Dict[str, Any],
) -> Dict[str, Any]:
    issue_type = str(ticket.get("issue_type", "general_support") or "general_support")
    triage = triage or {}
    hard_decision = hard_decision or {}
    final_action = final_action or {}
    executed = executed or {}
    history = history or {}
    brain_rules = brain_rules or []

    complexity = int(triage.get("complexity", 0) or 0)
    class_conf = round(min(0.99, 0.55 + complexity / 200.0), 2)
    dup_hint = issue_type == "billing_duplicate_charge" or "duplicate" in str(ticket.get("issue", "")).lower()
    issue_signal = (
        f"Matched {_human_issue_label(issue_type)} pattern"
        + (" with duplicate-charge wording" if dup_hint else "")
    )

    risk_level = str(final_action.get("risk_level", triage.get("risk_level", "medium")) or "medium")
    urgency = int(triage.get("urgency", 0) or 0)
    churn = int(triage.get("churn_risk", 0) or 0)
    abuse_like = int(triage.get("abuse_likelihood", 0) or 0)
    refund_hist = int(history.get("refund_count", 0) or 0)
    risk_bits = []
    if refund_hist >= 3:
        risk_bits.append("repeat refund history detected")
    if int(history.get("abuse_score", 0) or 0) >= 2:
        risk_bits.append("elevated abuse signals")
    risk_signal = f"{risk_level.capitalize()} risk"
    if risk_bits:
        risk_signal += " — " + ", ".join(risk_bits)

    hard_act = str(hard_decision.get("action", "none") or "none").lower()
    policy_triggered = hard_act != "none"
    policy_rule = str(hard_decision.get("reason", "") or "").strip() or "No hard policy lane fired"
    if issue_type == "billing_duplicate_charge" and policy_triggered:
        policy_rule = "Duplicate-charge protection"
    overridable = not bool(final_action.get("requires_approval", False)) and hard_act in {"none", "credit"}
    policy_signal = (
        "Hard policy applied — " + str(hard_decision.get("reason", "policy routing")) if policy_triggered else "No hard policy override — LLM/local path drove the motion"
    )

    repeat_customer = bool(history.get("repeat_customer", False))
    refund_count = int(history.get("refund_count", 0) or 0)
    abuse_score = int(history.get("abuse_score", 0) or 0)
    sentiment_now = int(ticket.get("sentiment", 5) or 5)
    sentiment_avg = float(history.get("sentiment_avg", 5.0) or 5.0)
    if sentiment_now < sentiment_avg - 0.75:
        trend = "declining"
    elif sentiment_now > sentiment_avg + 0.75:
        trend = "improving"
    else:
        trend = "stable"
    mem_signal = (
        f"{'Repeat' if repeat_customer else 'New'} customer · {refund_count} prior refunds · abuse score {abuse_score}"
    )

    applied_learned = bool(learned_action) and str(hard_decision.get("action", "none") or "none") == "none"
    trigger = None
    weight = None
    if applied_learned and brain_rules:
        trigger = str(brain_rules[0].get("trigger", "") or "") or None
        try:
            weight = float(brain_rules[0].get("weight", 0) or 0)
        except Exception:
            weight = None
    learned_signal = (
        f"Learned rule {trigger} applied (weight {weight})" if applied_learned and trigger else "No learned rule override applied"
    )

    requires = bool(final_action.get("requires_approval", False))
    fact_action = str(final_action.get("action", "none") or "none").lower()
    amount = float(final_action.get("amount", 0) or 0)
    appr_reasons: list[str] = []
    threshold: str | None = None
    if requires and fact_action in {"refund", "charge"}:
        appr_reasons.append("Refund or charge motion requires operator approval before execution.")
        threshold = f"${MAX_APPROVAL_THRESHOLD:.0f}"
    elif requires and fact_action == "credit" and amount > float(MAX_APPROVAL_THRESHOLD):
        appr_reasons.append(f"Credit amount exceeds ${MAX_APPROVAL_THRESHOLD:.0f} approval threshold.")
        threshold = f"${MAX_APPROVAL_THRESHOLD:.0f}"
    elif requires:
        appr_reasons.append("Risk or policy flags require explicit operator approval.")
    if abuse_score >= 2:
        appr_reasons.append(f"Abuse score {abuse_score} keeps a human gate recommended.")
        threshold = threshold or "abuse_score >= 2"
    appr_reason = " ".join(appr_reasons) if appr_reasons else "No approval gate on this path."

    execution_tier = compute_execution_tier(
        fact_action,
        amount,
        float(confidence or 0),
        float(quality or 0),
        risk_level,
        abuse_score,
        refund_count,
        str(ticket.get("operator_mode", "balanced") or "balanced"),
        requires,
    )

    summary_parts = [
        f"{_human_issue_label(issue_type)} with {risk_level} risk",
        f"urgency {urgency} and churn exposure near {churn}",
        mem_signal + ".",
    ]
    if policy_triggered:
        summary_parts.append(str(hard_decision.get("reason", "Hard policy fired.")))
    if applied_learned and trigger:
        summary_parts.append(f"Top learned signal: {trigger}.")
    if requires:
        summary_parts.append(appr_reason)
    summary_parts.append(
        f"Projected value: {impact_projection.get('type', 'saved')} · "
        f"${float(impact_projection.get('money_saved', 0) or 0):.0f} surfaced · "
        f"~{int(impact_projection.get('agent_minutes_saved', 0) or 0)} min saved."
    )
    summary_parts.append(f"Execution posture: {execution_tier.replace('_', ' ')}.")
    summary = " ".join(summary_parts)

    return {
        "issue_classification": {
            "type": issue_type,
            "confidence": class_conf,
            "signal": issue_signal,
        },
        "risk_assessment": {
            "level": risk_level,
            "urgency": urgency,
            "churn_risk": churn,
            "abuse_likelihood": abuse_like,
            "signal": risk_signal,
        },
        "policy_influence": {
            "triggered": policy_triggered,
            "rule": policy_rule,
            "overridable": overridable,
            "signal": policy_signal,
        },
        "memory_influence": {
            "repeat_customer": repeat_customer,
            "refund_count": refund_count,
            "abuse_score": abuse_score,
            "sentiment_trend": trend,
            "signal": mem_signal,
        },
        "learned_rule_influence": {
            "applied": applied_learned,
            "trigger": trigger,
            "weight": weight,
            "signal": learned_signal,
        },
        "approval_rationale": {
            "required": requires,
            "reason": appr_reason,
            "threshold": threshold,
        },
        "projected_impact": {
            "type": str(impact_projection.get("type", "saved") or "saved"),
            "amount": float(impact_projection.get("amount", 0) or 0),
            "money_saved": float(impact_projection.get("money_saved", 0) or 0),
            "agent_minutes_saved": int(impact_projection.get("agent_minutes_saved", 0) or 0),
            "auto_resolved": bool(impact_projection.get("auto_resolved", False)),
            "revenue_at_risk": float(impact_projection.get("revenue_at_risk", 0) or 0),
            "revenue_saved": float(impact_projection.get("revenue_saved", 0) or 0),
            "churn_risk_delta": float(impact_projection.get("churn_risk_delta", 0) or 0),
            "refund_cost": float(impact_projection.get("refund_cost", 0) or 0),
            "time_saved": float(impact_projection.get("time_saved", 0) or 0),
            "confidence_band": dict(impact_projection.get("confidence_band") or {}),
        },
        "execution_tier": execution_tier,
        "summary": summary,
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
    learned_action: Dict[str, Any] | None = None,
    brain_rules: list[Dict[str, Any]] | None = None,
    hard_decision: Dict[str, Any] | None = None,
    pattern_expectation: dict | None = None,
    outcome_key: str | None = None,
    human_approved: bool = False,
) -> Dict[str, Any]:
    conf_for_impact = float(clamp_confidence(final_action.get("confidence", 0.9), 0.9))
    impact = merge_impact_with_business_projection(ticket, final_action, confidence=conf_for_impact)
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

    try:
        from actions import compute_execution_tier as _compute_exec_tier

        _exec_tier = _compute_exec_tier(
            action=str(decision["action"]),
            amount=float(decision.get("amount", 0) or 0),
            confidence=float(decision.get("confidence", 0.9) or 0.9),
            quality=float(quality or 0),
            risk_level=str(decision.get("risk_level", "medium") or "medium"),
            abuse_score=int(history.get("abuse_score", 0) or 0),
            refund_count=int(history.get("refund_count", 0) or 0),
            operator_mode=str(ticket.get("operator_mode", "balanced") or "balanced"),
            requires_approval=bool(decision.get("requires_approval", False)),
        )
    except Exception:
        _exec_tier = "approval_required"

    impact_projection = {
        "type": str(impact.get("type", "saved") or "saved"),
        "amount": float(impact.get("amount", 0) or 0),
        "money_saved": float(impact.get("money_saved", 0) or 0),
        "auto_resolved": bool(impact.get("auto_resolved", decision["action"] in {"refund", "credit", "none"})),
        "agent_minutes_saved": int(impact.get("agent_minutes_saved", 6 if decision["action"] != "review" else 0) or 0),
        "signals": list(impact.get("signals", [])) if isinstance(impact.get("signals", []), list) else [],
        "revenue_at_risk": float(impact.get("revenue_at_risk", 0) or 0),
        "revenue_saved": float(impact.get("revenue_saved", 0) or 0),
        "churn_risk_delta": float(impact.get("churn_risk_delta", 0) or 0),
        "refund_cost": float(impact.get("refund_cost", 0) or 0),
        "time_saved": float(impact.get("time_saved", 0) or 0),
        "confidence_band": dict(impact.get("confidence_band") or {}),
    }

    hd = hard_decision if hard_decision is not None else final_action
    br_list = brain_rules or []
    conf_val = float(final_action.get("confidence", decision.get("confidence", 0.9)) or 0.9)
    decision_explanation = build_decision_explanation(
        ticket=ticket,
        triage=triage,
        hard_decision=hd,
        learned_action=learned_action,
        final_action=final_action,
        executed=executed,
        history=history,
        brain_rules=br_list,
        confidence=conf_val,
        quality=float(quality or 0),
        impact_projection=impact_projection,
    )
    decision_explanation["execution_tier"] = _exec_tier
    execution_tier = _exec_tier

    try:
        decision_explainability = build_decision_explainability(
            ticket=ticket,
            triage=triage,
            hard_decision=hd,
            learned_action=learned_action,
            final_action=final_action,
            executed=executed,
            history=history,
            top_rules=br_list,
            confidence=conf_val,
            quality=float(quality or 0),
            pattern_expectation=pattern_expectation,
        )
    except Exception:
        decision_explainability = None

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
        "decision_explanation": decision_explanation,
        "decision_explainability": decision_explainability,
        "execution_tier": execution_tier,
        "outcome_key": outcome_key,
        "audit_summary": build_audit_summary_payload(
            proposed_action=final_action,
            executed=executed,
            outcome_key=outcome_key,
            human_approved=human_approved,
            issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        ),
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
        _blocked_audit = build_audit_summary_payload(
            proposed_action={
                "action": "none",
                "amount": 0,
                "reason": "blocked_input",
                "requires_approval": False,
            },
            executed={
                "action": "none",
                "amount": 0,
                "tool_status": "blocked",
                "tool_result": {"status": "blocked"},
            },
            outcome_key=None,
            human_approved=False,
            issue_type="blocked",
        )
        _blocked_audit["trace"] = [
            "Request did not pass safety screening.",
            "Why: Input blocked by the security layer.",
            "Approval: Not applicable — nothing was executed.",
            "What ran: No action — blocked",
        ]
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
            decision_explanation=None,
            decision_explainability=None,
            execution_tier="assist_only",
            outcome_key=None,
            audit_summary=_blocked_audit,
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
    llm_used = False

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
            llm_used = True
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
    quality = compute_quality(confidence, triage, executed, user_memory, llm_used)

    # Log the real outcome — this feeds the learning loop with verified API results
    _outcome_key = (
        f"{user_id}"
        f":{str(ticket.get('issue_type', ''))[:20]}"
        f":{uuid.uuid4().hex[:12]}"
    )
    _tool_result = executed.get("tool_result") or {"status": executed.get("tool_status", "unknown")}
    _log_outcome(
        outcome_key=_outcome_key,
        user_id=user_id,
        action=str(executed.get("action", "none") or "none"),
        amount=float(executed.get("amount", 0) or 0),
        issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        tool_result=_tool_result,
        auto_resolved=bool(executed.get("action", "none") in {"refund", "credit", "none"}),
        approved_by_human=False,
    )

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

    try:
        from learning import get_pattern_expectation as _get_pattern_expectation

        _pattern_exp = _get_pattern_expectation(ticket, final_payload)
    except Exception:
        _pattern_exp = None

    update_memory(user_id, ticket, customer_message, final_payload)
    learn_from_ticket(ticket, final_payload, executed, outcome_key=_outcome_key)
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
        learned_action=learned_action,
        brain_rules=top_rules,
        hard_decision=hard_decision,
        pattern_expectation=_pattern_exp,
        outcome_key=_outcome_key,
        human_approved=False,
    )
