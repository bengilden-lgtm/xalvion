from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger("xalvion")

from actions import (
    apply_learned_rules,
    blend_llm_and_structural_confidence,
    build_decision_confidence_breakdown,
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

    def log_event(user_input, response, confidence, quality, **kwargs):  # noqa: ANN001
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
    from outcome_store import get_decision_outcome_stats as _get_decision_outcome_stats
    from outcome_store import log_outcome as _log_outcome
except Exception as _outcome_store_imp_err:
    logger.warning("outcome_store.log_outcome unavailable", exc_info=True)

    def _log_outcome(
        outcome_key,
        user_id,
        action,
        amount,
        issue_type,
        tool_result,
        auto_resolved=True,
        approved_by_human=False,
        is_simulated=False,
        execution_layer="agent_tool",
    ):
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def _get_decision_outcome_stats(issue_type, action, *, limit=300):
        return {
            "similar_case_count": 0,
            "historical_success_rate": None,
            "historical_reopen_rate": None,
            "outcome_confidence_band": "medium",
            "failure_rate": None,
            "reverse_rate": None,
            "dispute_rate": None,
        }


from agent.execution import execute_action, normalize_action_payload, should_attach_order_context
from agent.formatters import normalize_text, polish_message
from agent.llm import sovereign_llm_attempt
from agent.response_builder import (
    _canonicalize_result,
    _trace,
    build_audit_summary_payload,
    build_sovereign_prompt,
    compute_quality,
    rewrite_output_for_issue,
)

# governor.py (final authority layer) is optional; failures degrade to review, never crash.
try:
    from governor import gate_execution as _governor_gate_execution
except Exception as _gov_imp_err:
    logger.warning("governor.gate_execution unavailable; degrading to review", exc_info=True)

    def _governor_gate_execution(ticket, decision, memory=None):
        return {
            "execution_mode": "review",
            "requires_approval": True,
            "governor_reason": "Governor unavailable (soft-fail) — review required",
            "governor_risk_level": "high",
            "governor_risk_score": 5,
            "governor_factors": ["governor_import_failed"],
            "approved": False,
            "violations": ["governor_import_failed"],
        }


def _upgrade_risk_level(existing: str, incoming: str) -> str:
    """
    governor can only upgrade (tighten) risk, never downgrade.
    """
    order = {"low": 0, "medium": 1, "high": 2}
    a = str(existing or "").strip().lower()
    b = str(incoming or "").strip().lower()
    if a not in order:
        a = "medium"
    if b not in order:
        b = "medium"
    return b if order[b] > order[a] else a


def _apply_governor_overrides(*, ticket: Dict[str, Any], final_action: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    File: agent/orchestrator.py
    Apply governor gating between decisioning and execution.
    Conservative: any governor failure becomes review (requires_approval=True).
    """
    try:
        g = _governor_gate_execution(ticket, final_action, memory)
        if not isinstance(g, dict):
            raise TypeError("governor returned non-dict")
    except Exception:
        g = {
            "execution_mode": "review",
            "requires_approval": True,
            "governor_reason": "Governor error (soft-fail) — review required",
            "governor_risk_level": "high",
            "governor_risk_score": 5,
            "governor_factors": ["governor_call_failed"],
            "approved": False,
            "violations": ["governor_call_failed"],
        }

    # Governor is final authority over requires_approval and execution_mode.
    # (Additive fields are safe if absent on older clients.)
    next_action = dict(final_action or {})
    next_action["execution_mode"] = str(g.get("execution_mode", next_action.get("execution_mode", "")) or "")
    next_action["requires_approval"] = bool(g.get("requires_approval", True))

    # Upgrade risk if governor is stricter.
    next_action["risk_level"] = _upgrade_risk_level(next_action.get("risk_level", "medium"), g.get("governor_risk_level", "medium"))

    # Preserve governor audit fields on the decision payload.
    next_action["governor_reason"] = str(g.get("governor_reason", "") or "")
    next_action["governor_risk_score"] = int(g.get("governor_risk_score", 0) or 0)
    next_action["governor_risk_level"] = str(g.get("governor_risk_level", "") or "")
    next_action["governor_factors"] = list(g.get("governor_factors") or [])
    next_action["approved"] = bool(g.get("approved", False))
    next_action["violations"] = list(g.get("violations") or [])

    return next_action


def _sovereign_llm_parse_fallback(
    planned_action: Dict[str, Any],
    ticket: Dict[str, Any],
    triage: Dict[str, Any],
    confidence: float,
) -> Dict[str, Any]:
    """When the sovereign LLM returns no parseable JSON, continue with the structured planned decision (no local copy deck)."""
    pa = normalize_action_payload(planned_action, plan_tier=str(ticket.get("plan_tier", "free") or "free"))
    triage_d = triage if isinstance(triage, dict) else {}
    return {
        "customer_message": "",
        "customer_note": "",
        "internal_note": "LLM parse unavailable — continuing with structured planned decision.",
        "action": pa["action"],
        "amount": pa["amount"],
        "reason": str(planned_action.get("reason") or pa.get("reason") or ""),
        "confidence": float(confidence or 0.75),
        "risk_level": str(pa.get("risk_level") or triage_d.get("risk_level", "medium") or "medium"),
        "priority": str(pa.get("priority", "medium") or "medium"),
        "queue": str(pa.get("queue", "new") or "new"),
        "requires_approval": bool(pa.get("requires_approval", False)),
    }


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
        _blk_key = f"{user_id}:blocked:{uuid.uuid4().hex[:12]}"
        try:
            _log_outcome(
                outcome_key=_blk_key,
                user_id=user_id,
                action="none",
                amount=0.0,
                issue_type="blocked",
                tool_result={"status": "blocked"},
                auto_resolved=False,
                approved_by_human=False,
            )
        except Exception:
            logger.warning("outcome_log_blocked_failed", exc_info=True)
        payload["outcome_key"] = _blk_key
        return payload

    thinking_trace.append(_trace("sanitize_input", "done"))
    clean = clean or ""

    meta = meta or {}
    user_memory = get_user_memory(user_id)
    meta["customer_history"] = user_memory
    ticket = build_ticket(clean, user_id=user_id, meta=meta)
    ticket["request_context"] = ctx.model_dump()
    _plan_tier = str(ticket.get("plan_tier", "free") or "free")
    thinking_trace.append(_trace("build_ticket", "done"))

    order_info: Dict[str, Any] = {}
    ticket["order_data_connected"] = False
    if should_attach_order_context(str(ticket.get("issue_type", "general_support"))):
        order_info = get_order(ticket["customer"], clean)
        connected = bool(order_info.get("connected"))
        ticket["order_data_connected"] = connected
        if connected:
            if ticket.get("order_status") == "unknown":
                st = str(order_info.get("status") or "").strip()
                if st:
                    ticket["order_status"] = st
            tr = str(order_info.get("tracking", "") or "").strip()
            if tr:
                ticket["tracking"] = tr
            et = str(order_info.get("eta", "") or "").strip()
            if et:
                ticket["eta"] = et
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

    hard_decision = normalize_action_payload(system_decision(ticket), plan_tier=_plan_tier)
    thinking_trace.append(_trace("system_decision", "done"))
    learned_action = None
    top_rules = get_top_rule_objects(brain, 5)
    if hard_decision.get("action") == "none":
        learned_action = normalize_action_payload(apply_learned_rules(ticket, top_rules), plan_tier=_plan_tier) if top_rules else None
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
        parsed = _sovereign_llm_parse_fallback(planned_action, ticket, triage, confidence)
        thinking_trace.append(_trace("sovereign_llm_parse", "done", "structured_planned_action"))

    llm_payload = normalize_action_payload(parsed, plan_tier=_plan_tier)

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

    if execution_requires_operator_gate(
        final_action.get("action", "none"),
        final_action.get("amount", 0),
        plan_tier=_plan_tier,
    ):
        final_action = {**final_action, "requires_approval": True}

    # --- Outcome intelligence + structural confidence (before governor; governor may tighten further) ---
    try:
        _issue_t = str(ticket.get("issue_type", "general_support") or "general_support")
        _act_t = str(final_action.get("action", "none") or "none")
        _outcome_stats = _get_decision_outcome_stats(_issue_t, _act_t, limit=300)
        _pattern_pre = get_pattern_expectation(ticket, final_action)
        _breakdown = build_decision_confidence_breakdown(
            ticket,
            final_action,
            user_memory,
            _pattern_pre,
            _outcome_stats,
        )
        _blended = blend_llm_and_structural_confidence(
            confidence,
            _breakdown,
            int(_outcome_stats.get("similar_case_count") or 0),
        )
        final_action = {
            **final_action,
            "confidence": _blended,
            "decision_confidence_breakdown": _breakdown,
            "similar_case_count": int(_outcome_stats.get("similar_case_count") or 0),
            "historical_success_rate": _outcome_stats.get("historical_success_rate"),
            "historical_reopen_rate": _outcome_stats.get("historical_reopen_rate"),
            "outcome_confidence_band": str(_outcome_stats.get("outcome_confidence_band") or "medium"),
        }
        confidence = float(_blended)
    except Exception:
        logger.warning("outcome-aware confidence merge skipped", exc_info=True)

    # --- governor.py final authority layer (between decisioning and execution) ---
    # File: agent/orchestrator.py
    # Enforces a no-downgrade posture: governor can only add gates / tighten risk.
    final_action = _apply_governor_overrides(ticket=ticket, final_action=final_action, memory=user_memory or {})

    _gov_mode = str(final_action.get("execution_mode", "") or "").strip().lower()
    if _gov_mode == "blocked":
        # Blocked: do NOT execute live financial actions. Route to review safely.
        executed = {
            "action": "review",
            "amount": 0,
            "tool_result": {
                "status": "manual_review",
                "type": "governor_block",
                "message": str(final_action.get("governor_reason") or "Blocked by governor policy"),
                "violations": list(final_action.get("violations") or []),
            },
            "tool_status": "manual_review",
        }
        thinking_trace.append(_trace("governor_gate", "done", "blocked"))
    elif _gov_mode == "review":
        # Review: keep reply generation, but hold any tool execution behind approval gate.
        final_action = {**final_action, "requires_approval": True}
        try:
            executed = execute_action(ticket, final_action)
        except Exception as _exec_exc:
            logger.error(
                "execute_action_raised action=%s issue=%s error=%s",
                final_action.get("action"),
                ticket.get("issue_type"),
                str(_exec_exc)[:300],
                exc_info=True,
            )
            executed = {
                "action": final_action.get("action", "review"),
                "amount": 0,
                "tool_result": {
                    "status": "execution_error",
                    "is_simulated": False,
                    "verified": False,
                    "verified_success": False,
                    "error": str(_exec_exc)[:300],
                },
                "tool_status": "execution_error",
                "is_simulated": False,
                "verified_success": False,
            }
        thinking_trace.append(_trace("governor_gate", "done", "review"))
        thinking_trace.append(_trace("execute_action", "done", str(executed.get("tool_status", "no_action"))))
    else:
        # Auto: preserve existing behavior.
        try:
            executed = execute_action(ticket, final_action)
        except Exception as _exec_exc:
            logger.error(
                "execute_action_raised action=%s issue=%s error=%s",
                final_action.get("action"),
                ticket.get("issue_type"),
                str(_exec_exc)[:300],
                exc_info=True,
            )
            executed = {
                "action": final_action.get("action", "review"),
                "amount": 0,
                "tool_result": {
                    "status": "execution_error",
                    "is_simulated": False,
                    "verified": False,
                    "verified_success": False,
                    "error": str(_exec_exc)[:300],
                },
                "tool_status": "execution_error",
                "is_simulated": False,
                "verified_success": False,
            }
        thinking_trace.append(_trace("governor_gate", "done", "auto"))
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
    _is_simulated = bool(
        executed.get("is_simulated")
        or (isinstance(_tool_result, dict) and _tool_result.get("is_simulated"))
    )
    _verified_success = bool(
        executed.get("verified_success")
        or (isinstance(_tool_result, dict) and _tool_result.get("verified_success"))
    )
    _verified_ok = _verified_success and not _is_simulated
    _log_outcome(
        outcome_key=_outcome_key,
        user_id=user_id,
        action=_exec_act,
        amount=float(executed.get("amount", 0) or 0),
        issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
        tool_result=_tool_result,
        auto_resolved=(not _held_for_operator) and _exec_act in {"refund", "credit", "none"} and _verified_ok,
        approved_by_human=False,
        is_simulated=_is_simulated,
        execution_layer=str(executed.get("execution_layer", "agent_tool") or "agent_tool"),
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
    try:
        log_event(
            clean,
            customer_message,
            confidence,
            quality,
            issue_type=str(ticket.get("issue_type", "general_support") or "general_support"),
            action=str(final_payload.get("action", "none") or "none"),
            amount=float(final_payload.get("amount", 0) or 0),
            actor_principal=str(user_id or "")[:120],
        )
    except Exception:
        pass  # analytics write failure never blocks the response
    if quality > 0.92 and not _is_simulated:
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
