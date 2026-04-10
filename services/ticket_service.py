from __future__ import annotations

from typing import Any

from actions import build_ticket as build_support_ticket
from app_utils import (
    _clamp,
    _now_iso,
    _safe_channel,
    _safe_priority,
    _safe_queue,
    _safe_risk,
    _safe_source,
    _safe_status,
    get_plan_name,
)
from orm_models import ActionLog, Ticket
from sqlalchemy.orm import Session


def create_ticket_record(db: Session, user: Any, req: Any) -> Any:
    now = _now_iso()
    bootstrap_ticket = build_support_ticket(
        req.message,
        user_id=str(getattr(user, "username", "unknown") or "unknown"),
        meta={
            "sentiment": req.sentiment if req.sentiment is not None else 5,
            "ltv": req.ltv if req.ltv is not None else 0,
            "order_status": req.order_status if req.order_status is not None else "unknown",
            "plan_tier": get_plan_name(user),
            "operator_mode": "balanced",
            "channel": _safe_channel(req.channel),
            "source": _safe_source(req.source),
            "customer_history": {},
        },
    )
    ticket = Ticket(
        created_at=now,
        updated_at=now,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        channel=_safe_channel(req.channel),
        source=_safe_source(req.source),
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

    ticket.updated_at = _now_iso()
    ticket.status = _safe_status(status)
    ticket.queue = _safe_queue(raw_queue)
    ticket.priority = _safe_priority(decision.get("priority") or (result.get("meta") or {}).get("priority") or "medium")
    ticket.risk_level = _safe_risk(decision.get("risk_level") or "medium")
    ticket.issue_type = str(result.get("issue_type", "general_support") or "general_support")[:64]
    ticket.final_reply = str(result.get("reply", result.get("final", "")) or "")[:8000]
    ticket.internal_note = str(output.get("internal_note") or "")[:2000]
    ticket.action = action
    ticket.amount = float(result.get("amount", 0) or 0)
    ticket.confidence = float(result.get("confidence", 0) or 0)
    ticket.quality = float(result.get("quality", 0) or 0)
    ticket.requires_approval = int(bool(decision.get("requires_approval", False)))
    ticket.approved = 0
    ticket.urgency = _clamp(triage.get("urgency", 0), 0, 99)
    ticket.churn_risk = _clamp(triage.get("churn_risk", 0), 0, 99)
    ticket.refund_likelihood = _clamp(triage.get("refund_likelihood", 0), 0, 99)
    ticket.abuse_likelihood = _clamp(triage.get("abuse_likelihood", 0), 0, 99)
    ticket.complexity = _clamp(triage.get("complexity", 0), 0, 99)

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
    entry = ActionLog(
        timestamp=_now_iso(),
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
    base = serialize_ticket(ticket)
    log = (
        db.query(ActionLog)
        .filter(ActionLog.ticket_id == ticket.id)
        .order_by(ActionLog.id.desc())
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


def generate_simulated_inbox_tickets(*, count: int = 6, seed: str | None = None) -> list[dict[str, Any]]:
    """Generate realistic-looking inbound tickets for the workspace inbox layer.

    Additive / safe: used only when there is no upstream integration providing real tickets.
    """
    import hashlib
    import random
    import time

    count = int(count or 0)
    if count <= 0:
        return []
    count = min(24, max(1, count))

    seed_raw = (seed or "").strip()
    if not seed_raw:
        seed_raw = str(int(time.time() // 60))
    digest = hashlib.sha256(seed_raw.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:12], 16))

    templates: list[dict[str, Any]] = [
        {
            "issue_type": "refund_request",
            "subject": "I want a refund — this is unacceptable",
            "message": "I’ve been trying to resolve this for days. Please refund my order immediately. I’m done with this service.",
            "churn_risk": (78, 96),
            "refund_likelihood": (70, 95),
            "urgency": (70, 92),
            "complexity": (22, 55),
            "ltv": (180, 650),
        },
        {
            "issue_type": "duplicate_charge",
            "subject": "Charged twice — need this fixed now",
            "message": "I was charged twice for the same order. Can you reverse the extra charge today? This is really frustrating.",
            "churn_risk": (55, 86),
            "refund_likelihood": (65, 92),
            "urgency": (62, 90),
            "complexity": (25, 60),
            "ltv": (300, 900),
        },
        {
            "issue_type": "late_delivery",
            "subject": "Package is late and I need an update",
            "message": "My package was supposed to arrive yesterday. Can you tell me where it is and when it’ll be delivered?",
            "churn_risk": (35, 68),
            "refund_likelihood": (20, 55),
            "urgency": (55, 85),
            "complexity": (20, 55),
            "ltv": (120, 480),
        },
        {
            "issue_type": "cancel_subscription",
            "subject": "Please cancel my subscription",
            "message": "I’d like to cancel my subscription effective immediately. Also confirm I won’t be billed again.",
            "churn_risk": (70, 96),
            "refund_likelihood": (25, 60),
            "urgency": (40, 78),
            "complexity": (18, 50),
            "ltv": (700, 2400),
        },
        {
            "issue_type": "damaged_item",
            "subject": "Item arrived damaged",
            "message": "My order arrived damaged. I can share photos. What’s the fastest way to get a replacement?",
            "churn_risk": (45, 78),
            "refund_likelihood": (35, 70),
            "urgency": (52, 82),
            "complexity": (28, 62),
            "ltv": (250, 1100),
        },
        {
            "issue_type": "address_change",
            "subject": "Need to change shipping address",
            "message": "I entered the wrong shipping address. Can you update it before it ships? Order number is in my account.",
            "churn_risk": (18, 42),
            "refund_likelihood": (8, 28),
            "urgency": (48, 78),
            "complexity": (18, 45),
            "ltv": (80, 420),
        },
    ]

    def rrange(lo_hi: tuple[int, int]) -> int:
        lo, hi = lo_hi
        return int(rng.randint(int(lo), int(hi)))

    now_ms = int(time.time() * 1000)
    out: list[dict[str, Any]] = []
    for i in range(count):
        t = rng.choice(templates)
        churn = rrange(t["churn_risk"])
        refund = rrange(t["refund_likelihood"])
        urgency = rrange(t["urgency"])
        complexity = rrange(t["complexity"])
        ltv = float(rrange(t["ltv"]))

        risk_score = max(churn, refund)
        if risk_score >= 80 or (refund >= 72 and urgency >= 68):
            risk_level = "high"
        elif risk_score >= 55:
            risk_level = "medium"
        else:
            risk_level = "low"

        if urgency >= 78:
            priority = "high"
        elif urgency >= 58:
            priority = "medium"
        else:
            priority = "low"

        sid = f"sim-{digest[:6]}-{(now_ms // 1000) % 100000:05d}-{i+1}"
        out.append(
            {
                "id": sid,
                "source": "sim",
                "created_at": now_ms - (i * 19_000),
                "subject": str(t["subject"]),
                "customer_message": str(t["message"]),
                "issue_type": str(t["issue_type"]),
                "queue": "incoming",
                "status": "new",
                "priority": priority,
                "risk_level": risk_level,
                "urgency": urgency,
                "churn_risk": churn,
                "refund_likelihood": refund,
                "abuse_likelihood": 0,
                "complexity": complexity,
                "ltv": round(float(ltv), 2),
            }
        )
    return out
