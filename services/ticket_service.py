from __future__ import annotations

from typing import Any

from actions import build_ticket as build_support_ticket
from sqlalchemy.orm import Session


def create_ticket_record(db: Session, user: Any, req: Any) -> Any:
    import app as _app

    now = _app._now_iso()
    bootstrap_ticket = build_support_ticket(
        req.message,
        user_id=str(getattr(user, "username", "unknown") or "unknown"),
        meta={
            "sentiment": req.sentiment if req.sentiment is not None else 5,
            "ltv": req.ltv if req.ltv is not None else 0,
            "order_status": req.order_status if req.order_status is not None else "unknown",
            "plan_tier": _app.get_plan_name(user),
            "operator_mode": "balanced",
            "channel": _app._safe_channel(req.channel),
            "source": _app._safe_source(req.source),
            "customer_history": {},
        },
    )
    ticket = _app.Ticket(
        created_at=now,
        updated_at=now,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        channel=_app._safe_channel(req.channel),
        source=_app._safe_source(req.source),
        subject=(req.message or "")[:300],
        customer_message=(req.message or "")[:10000],
        status="new",
        queue="new",
        priority="medium",
        risk_level="medium",
        issue_type=str(bootstrap_ticket.get("issue_type", "general_support") or "general_support")[:64],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_from_result(db: Session, ticket: Any, result: dict[str, Any]) -> Any:
    import app as _app

    decision = result.get("decision") or {}
    triage = result.get("triage") or {}
    output = result.get("output") or {}
    action = str(result.get("action", "none") or "none")
    raw_queue = str(decision.get("queue", "new") or "new")
    tool_status = str(result.get("tool_status", "") or "").lower()

    if tool_status in {"pending_approval", "manual_review"}:
        status = "waiting"
    elif action in {"refund", "credit", "none"}:
        status = "resolved"
    else:
        status = "escalated"

    if raw_queue == "resolved":
        status = "resolved"

    ticket.updated_at = _app._now_iso()
    ticket.status = _app._safe_status(status)
    ticket.queue = _app._safe_queue(raw_queue)
    ticket.priority = _app._safe_priority(decision.get("priority") or (result.get("meta") or {}).get("priority") or "medium")
    ticket.risk_level = _app._safe_risk(decision.get("risk_level") or "medium")
    ticket.issue_type = str(result.get("issue_type", "general_support") or "general_support")[:64]
    ticket.final_reply = str(result.get("reply", result.get("final", "")) or "")[:8000]
    ticket.internal_note = str(output.get("internal_note") or "")[:2000]
    ticket.action = action
    ticket.amount = float(result.get("amount", 0) or 0)
    ticket.confidence = float(result.get("confidence", 0) or 0)
    ticket.quality = float(result.get("quality", 0) or 0)
    ticket.requires_approval = int(bool(decision.get("requires_approval", False)))
    ticket.approved = 0
    ticket.urgency = _app._clamp(triage.get("urgency", 0), 0, 99)
    ticket.churn_risk = _app._clamp(triage.get("churn_risk", 0), 0, 99)
    ticket.refund_likelihood = _app._clamp(triage.get("refund_likelihood", 0), 0, 99)
    ticket.abuse_likelihood = _app._clamp(triage.get("abuse_likelihood", 0), 0, 99)
    ticket.complexity = _app._clamp(triage.get("complexity", 0), 0, 99)

    db.commit()
    db.refresh(ticket)
    return ticket


def log_action(
    db: Session,
    *,
    username: str,
    ticket_id: int | None = None,
    action: str,
    amount: float,
    issue_type: str,
    reason: str,
    status: str,
    confidence: float,
    quality: float,
    message_snippet: str,
    requires_approval: bool = False,
    approved: bool = False,
) -> Any:
    import app as _app

    entry = _app.ActionLog(
        timestamp=_app._now_iso(),
        username=username,
        ticket_id=ticket_id,
        action=action,
        amount=round(float(amount or 0), 2),
        issue_type=issue_type,
        reason=(reason or "")[:500],
        status=status,
        confidence=round(float(confidence or 0), 4),
        quality=round(float(quality or 0), 4),
        message_snippet=(message_snippet or "")[:200],
        requires_approval=int(requires_approval),
        approved=int(approved),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def serialize_ticket(ticket: Any) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "username": ticket.username,
        "channel": ticket.channel,
        "source": ticket.source,
        "status": ticket.status,
        "queue": ticket.queue,
        "priority": ticket.priority,
        "risk_level": ticket.risk_level,
        "issue_type": ticket.issue_type,
        "subject": ticket.subject,
        "customer_message": ticket.customer_message,
        "final_reply": ticket.final_reply,
        "internal_note": ticket.internal_note,
        "action": ticket.action,
        "amount": ticket.amount,
        "confidence": ticket.confidence,
        "quality": ticket.quality,
        "requires_approval": bool(ticket.requires_approval),
        "approved": bool(ticket.approved),
        "urgency": ticket.urgency,
        "churn_risk": ticket.churn_risk,
        "refund_likelihood": ticket.refund_likelihood,
        "abuse_likelihood": ticket.abuse_likelihood,
        "complexity": ticket.complexity,
    }


def serialize_ticket_with_log(ticket: Any, db: Session) -> dict[str, Any]:
    import app as _app

    base = serialize_ticket(ticket)
    log = (
        db.query(_app.ActionLog)
        .filter(_app.ActionLog.ticket_id == ticket.id)
        .order_by(_app.ActionLog.id.desc())
        .first()
    )
    if log:
        base["action_log"] = {
            "log_id": log.id,
            "action": log.action,
            "amount": log.amount,
            "status": log.status,
            "reason": log.reason,
            "confidence": log.confidence,
            "quality": log.quality,
            "requires_approval": bool(log.requires_approval),
            "approved": bool(log.approved),
            "timestamp": log.timestamp,
        }
    else:
        base["action_log"] = None
    return base
