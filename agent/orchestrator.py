from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger("xalvion")

from actions import (
    apply_learned_rules,
    build_ticket,
    execution_requires_operator_gate,
    system_decision,
    triage_ticket,
)
from brain import add_rule, get_top_rule_objects, load_brain, save_brain, update_system_prompt
from memory import get_prompt_memory, get_user_memory, update_memory
from security import sanitize_input
from tools import get_order
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
except Exception as _analytics_imp_err:
    logger.warning(
        "analytics.log_event unavailable; events will not be recorded",
        exc_info=True,
    )

    def log_event(user_input, response, confidence, quality, **kwargs):
        return None


try:
    from feedback import process_feedback
except Exception as _feedback_imp_err:
    logger.warning("feedback.process_feedback unavailable", exc_info=True)

    def process_feedback(user_input, response, quality):
        raise RuntimeError("feedback module unavailable") from _feedback_imp_err


try:
    from learning import get_pattern_expectation, learn_from_ticket
except Exception as _learning_imp_err:
    logger.warning("learning module unavailable for learn_from_ticket / get_pattern_expectation", exc_info=True)

    def learn_from_ticket(ticket, decision, outcome, outcome_key=None):
        raise RuntimeError("learning.learn_from_ticket unavailable") from _learning_imp_err

    def get_pattern_expectation(ticket, decision):
        raise RuntimeError("learning.get_pattern_expectation unavailable") from _learning_imp_err


try:
    from outcome_store import log_outcome as _log_outcome
except Exception as _outcome_store_imp_err:
    logger.warning("outcome_store.log_outcome unavailable", exc_info=True)

    def _log_outcome(outcome_key, user_id, action, amount, issue_type, tool_result, auto_resolved=True, approved_by_human=False):
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err


from agent.execution import execute_action, normalize_action_payload, should_attach_order_context
from agent.llm import sovereign_llm_attempt
from agent.response_builder import (
    _canonicalize_result,
    _trace,
    build_audit_summary_payload,
    build_sovereign_prompt,
    compute_quality,
    conversational_reply,
    is_conversational_message,
    local_fallback_reply,
    normalize_text,
    polish_message,
    rewrite_output_for_issue,
)


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

    parsed, mode, confidence, quality, llm_used = sovereign_llm_attempt(clean, brain, prompt, thinking_trace)

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

    if execution_requires_operator_gate(final_action.get("action", "none"), final_action.get("amount", 0)):
        final_action = {**final_action, "requires_approval": True}

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
    _exec_ts = str(executed.get("tool_status", "") or "").lower()
    _exec_act = str(executed.get("action", "none") or "none")
    _held_for_operator = _exec_ts in {"pending_approval", "manual_review", "approved_pending_execution"}
    _log_outcome(
        outcome_key=_outcome_key,
        user_id=user_id,
        action=_exec_act,
        amount=float(executed.get("amount", 0) or 0),
        issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        tool_result=_tool_result,
        auto_resolved=(not _held_for_operator) and _exec_act in {"refund", "credit", "none"},
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

    _pattern_exp = get_pattern_expectation(ticket, final_payload)

    update_memory(user_id, ticket, customer_message, final_payload)
    learn_from_ticket(ticket, final_payload, executed, outcome_key=_outcome_key)
    process_feedback(clean, customer_message, quality)
    log_event(
        clean,
        customer_message,
        confidence,
        quality,
        issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        action=str(final_payload.get("action", "none") or "none"),
        amount=float(final_payload.get("amount", 0) or 0),
    )
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
