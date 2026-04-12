from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import case as _case, func
from sqlalchemy.orm import Session

import app as app_mod
from app_utils import _me_capacity_message, _tier_upgrade_unlocks

router = APIRouter(tags=["support"])

logger = logging.getLogger("xalvion.api")


def _ticket_owner_key(user: app_mod.User, x_guest_client: str | None) -> str | None:
    """DB ``Ticket.username`` / ``ActionLog.username`` scope for the current request."""
    if app_mod.is_session_guest(user):
        return app_mod.normalize_guest_client_id(x_guest_client)
    return str(getattr(user, "username", "") or "") or None


def _stream_usage_warning_payload(username: str) -> dict[str, Any] | None:
    if not username or username in {"guest", "dev_user", ""}:
        return None
    try:
        with app_mod.db_session() as db:
            row = db.query(app_mod.User).filter(app_mod.User.username == username).first()
            if not row:
                return None
            db.expunge(row)
            user_row = row
        summary = app_mod.get_usage_summary(user_row)
        limit = int(summary["limit"])
        if limit >= 10**9:
            return None
        usage = int(summary["usage"])
        pct = float(usage) / float(max(1, limit))
        if pct < 0.75:
            return None
        tier = app_mod.get_public_plan_name(user_row)
        if str(tier).strip().lower() in {"elite", "dev"}:
            return None
        at_limit = usage >= limit
        rem = int(summary["remaining"])
        return {
            "approaching_limit": True,
            "at_limit": at_limit,
            "usage_pct": round(pct, 2),
            "remaining": rem,
            "upgrade_unlocks": _tier_upgrade_unlocks(tier),
            "tickets_handled": int(summary.get("usage", 0) or 0),
            "capacity_message": _me_capacity_message(tier, rem),
        }
    except Exception:
        return None


def _apply_ticket_search(q, search_term: str):
    """
    Full-text search across ticket columns.
    TODO: Replace ilike scan with FTS (tsvector+GIN for Postgres,
    FTS5 for SQLite) before ticket volume exceeds 50k rows.
    """
    term = f"%{search_term}%"
    return q.filter(
        app_mod.Ticket.subject.ilike(term)
        | app_mod.Ticket.customer_message.ilike(term)
        | app_mod.Ticket.final_reply.ilike(term)
        | app_mod.Ticket.internal_note.ilike(term)
        | app_mod.Ticket.issue_type.ilike(term)
    )


@router.get("/tickets")
def list_tickets(
    limit: int = 50,
    offset: int = 0,
    page: int | None = None,
    page_size: int | None = None,
    queue: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    risk_level: str | None = None,
    issue_type: str | None = None,
    username: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    user: app_mod.User = Depends(app_mod.get_current_user),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(app_mod.get_db),
):
    if page_size is not None:
        limit = page_size
    if page is not None:
        offset = max(0, (page - 1)) * max(1, limit)

    q = db.query(app_mod.Ticket)
    is_admin = getattr(user, "username", "") == app_mod.ADMIN_USERNAME
    owner_key = _ticket_owner_key(user, x_guest_client)

    if not is_admin:
        if app_mod.is_session_guest(user) and not owner_key:
            return {
                "operator_mode": app_mod.get_operator_mode(db),
                "total": 0,
                "limit": max(1, min(limit, 200)),
                "offset": max(0, offset),
                "page": (offset // max(1, min(limit, 200))) + 1 if limit > 0 else 1,
                "page_size": max(1, min(limit, 200)),
                "has_more": False,
                "items": [],
                "tickets": [],
            }
        q = q.filter(app_mod.Ticket.username == owner_key)
    elif username:
        q = q.filter(app_mod.Ticket.username == username.strip())

    if queue:
        q = q.filter(app_mod.Ticket.queue == app_mod._safe_queue(queue))
    if status:
        q = q.filter(app_mod.Ticket.status == app_mod._safe_status(status))
    if priority:
        q = q.filter(app_mod.Ticket.priority == app_mod._safe_priority(priority))
    if risk_level:
        q = q.filter(app_mod.Ticket.risk_level == app_mod._safe_risk(risk_level))
    if issue_type:
        q = q.filter(app_mod.Ticket.issue_type == issue_type.strip().lower()[:64])

    if search and len(search.strip()) >= 2:
        q = _apply_ticket_search(q, search.strip())

    sort_map = {
        "newest": app_mod.Ticket.id.desc(),
        "oldest": app_mod.Ticket.id.asc(),
        "urgency": app_mod.Ticket.urgency.desc(),
        "churn_risk": app_mod.Ticket.churn_risk.desc(),
        "priority": _case(
            (app_mod.Ticket.priority == "high", 3),
            (app_mod.Ticket.priority == "medium", 2),
            (app_mod.Ticket.priority == "low", 1),
            else_=0,
        ).desc(),
    }
    q = q.order_by(sort_map.get(sort, app_mod.Ticket.id.desc()))

    total = q.count()
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    rows = q.offset(offset).limit(limit).all()
    curr_page = (offset // limit) + 1 if limit > 0 else 1

    items = [app_mod.serialize_ticket(r) for r in rows]
    return {
        "operator_mode": app_mod.get_operator_mode(db),
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": curr_page,
        "page_size": limit,
        "has_more": (offset + limit) < total,
        "items": items,
        "tickets": items,
    }


@router.get("/tickets/recent")
def recent_tickets(
    limit: int = 5,
    user: app_mod.User = Depends(app_mod.get_current_user),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(app_mod.get_db),
):
    limit = max(1, min(int(limit or 5), 10))
    owner_key = _ticket_owner_key(user, x_guest_client)

    # Authenticated users: scope to account (admin can see own only here; list_tickets supports admin browse).
    if not owner_key:
        if app_mod.is_session_guest(user):
            return {"items": [], "tickets": []}
        raise HTTPException(status_code=401, detail="Authentication required")
    q = db.query(app_mod.Ticket).filter(app_mod.Ticket.username == owner_key)

    rows = q.order_by(app_mod.Ticket.updated_at.desc(), app_mod.Ticket.id.desc()).limit(limit).all()
    items = [app_mod.serialize_ticket(r) for r in rows]
    return {"items": items, "tickets": items}


@router.get("/tickets/queues")
def ticket_queue_counts(
    user: app_mod.User = Depends(app_mod.get_current_user),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(app_mod.get_db),
):
    is_admin = getattr(user, "username", "") == app_mod.ADMIN_USERNAME
    owner_key = _ticket_owner_key(user, x_guest_client)

    base_q = db.query(app_mod.Ticket.queue, func.count(app_mod.Ticket.id).label("cnt"))
    if not is_admin:
        if app_mod.is_session_guest(user) and not owner_key:
            return {
                "queues": {q: 0 for q in app_mod.VALID_QUEUES},
                "statuses": {s: 0 for s in app_mod.VALID_STATUSES},
                "operator_mode": app_mod.get_operator_mode(db),
            }
        base_q = base_q.filter(app_mod.Ticket.username == owner_key)

    queue_counts: dict[str, int] = {q: 0 for q in app_mod.VALID_QUEUES}
    for qname, cnt in base_q.group_by(app_mod.Ticket.queue).all():
        queue_counts[app_mod._safe_queue(qname or "new")] = int(cnt)

    base_s = db.query(app_mod.Ticket.status, func.count(app_mod.Ticket.id).label("cnt"))
    if not is_admin:
        base_s = base_s.filter(app_mod.Ticket.username == owner_key)

    status_counts: dict[str, int] = {s: 0 for s in app_mod.VALID_STATUSES}
    for sname, cnt in base_s.group_by(app_mod.Ticket.status).all():
        status_counts[app_mod._safe_status(sname or "new")] = int(cnt)

    return {
        "queues": queue_counts,
        "statuses": status_counts,
        "operator_mode": app_mod.get_operator_mode(db),
    }


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user: app_mod.User = Depends(app_mod.get_current_user),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(app_mod.get_db),
):
    ticket = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    owner_key = _ticket_owner_key(user, x_guest_client)
    if getattr(user, "username", "") != app_mod.ADMIN_USERNAME:
        if app_mod.is_session_guest(user) and not owner_key:
            raise HTTPException(status_code=403, detail="Forbidden")
        if ticket.username != owner_key:
            raise HTTPException(status_code=403, detail="Forbidden")
    return app_mod.serialize_ticket_with_log(ticket, db)


@router.post("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    req: app_mod.TicketStatusRequest,
    admin: app_mod.User = Depends(app_mod.require_admin),
    db: Session = Depends(app_mod.get_db),
):
    ticket = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if req.status:
        ticket.status = app_mod._safe_status(req.status, ticket.status)
    if req.queue:
        ticket.queue = app_mod._safe_queue(req.queue, ticket.queue)
    if req.priority:
        ticket.priority = app_mod._safe_priority(req.priority, ticket.priority)
    if req.internal_note:
        existing = (ticket.internal_note or "").strip()
        addition = (req.internal_note or "").strip()
        ticket.internal_note = (existing + "\n" + addition).strip() if existing else addition

    ticket.updated_at = app_mod._now_iso()
    db.commit()
    db.refresh(ticket)
    return app_mod.serialize_ticket(ticket)


@router.get("/tickets/pending-approvals")
def list_pending_ticket_approvals(
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    query = db.query(app_mod.Ticket).filter(app_mod.Ticket.requires_approval == 1, app_mod.Ticket.approved == 0)
    if getattr(user, "username", "") != app_mod.ADMIN_USERNAME:
        query = query.filter(app_mod.Ticket.username == user.username)

    tickets = query.order_by(app_mod.Ticket.updated_at.desc()).limit(50).all()
    return [app_mod.serialize_ticket_with_log(ticket, db) for ticket in tickets]


@router.post("/tickets/{ticket_id}/approve")
def approve_ticket(
    ticket_id: int,
    req: app_mod.ApprovalDecisionRequest,
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    ticket = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if getattr(user, "username", "") != app_mod.ADMIN_USERNAME and ticket.username != user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bool(ticket.requires_approval) or bool(ticket.approved):
        raise HTTPException(status_code=400, detail="No pending approval for this ticket")

    log = (
        db.query(app_mod.ActionLog)
        .filter(app_mod.ActionLog.ticket_id == ticket.id, app_mod.ActionLog.requires_approval == 1, app_mod.ActionLog.approved == 0)
        .order_by(app_mod.ActionLog.id.desc())
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Pending approval log not found")

    edited_reply = (req.final_reply or "").strip()
    if edited_reply:
        ticket.final_reply = edited_reply[:8000]

    app_mod.append_ticket_internal_note(ticket, req.internal_note or "")
    payload, log_status = app_mod.approve_ticket_action(ticket, log, req, user)

    ticket.updated_at = app_mod._now_iso()
    ticket.action = str(payload.get("action", ticket.action) or ticket.action)
    ticket.amount = float(payload.get("amount", ticket.amount) or ticket.amount)
    ticket.final_reply = str(payload.get("reply", payload.get("response", ticket.final_reply)) or ticket.final_reply)[:8000]
    ticket.status = app_mod._safe_status((payload.get("decision") or {}).get("status", "resolved"), "resolved")
    ticket.queue = app_mod._safe_queue((payload.get("decision") or {}).get("queue", "resolved"), "resolved")
    ticket.priority = app_mod._safe_priority((payload.get("decision") or {}).get("priority", ticket.priority or "high"), ticket.priority or "high")
    ticket.risk_level = app_mod._safe_risk((payload.get("decision") or {}).get("risk_level", ticket.risk_level or "medium"), ticket.risk_level or "medium")
    ticket.requires_approval = 0
    ticket.approved = 1
    app_mod.append_ticket_internal_note(ticket, f"Approved by {user.username} at {app_mod._now_iso()}")

    log.approved = 1
    log.requires_approval = 0
    log.status = log_status
    log.reason = str(payload.get("reason", log.reason) or log.reason)
    db.commit()
    db.refresh(ticket)
    db.refresh(log)

    response = app_mod.build_ticket_response_payload(ticket, log, db=db)
    response["message"] = f"Ticket {ticket.id} approved"
    try:
        pa = str(log.action or ticket.action or "none")
        pam = round(float(log.amount or ticket.amount or 0), 2)
        response["audit_summary"] = app_mod.build_audit_summary_payload(
            proposed_action={
                "action": pa,
                "amount": pam,
                "reason": str(log.reason or "") or "Policy-sensitive motion",
                "requires_approval": True,
            },
            executed={
                "action": str(payload.get("action", pa) or pa),
                "amount": float(payload.get("amount", pam) or pam),
                "tool_status": str(payload.get("tool_status", log_status)),
                "tool_result": payload.get("tool_result") if isinstance(payload.get("tool_result"), dict) else {},
            },
            outcome_key=None,
            human_approved=True,
            issue_type=str(ticket.issue_type or "general_support"),
        )
        tr = list((response.get("audit_summary") or {}).get("trace") or [])
        response["audit_summary"]["trace"] = tr + [
            "Accountability: Operator sign-off recorded in workspace before release.",
        ]
    except Exception:
        pass
    return response


@router.post("/tickets/{ticket_id}/reject")
def reject_ticket(
    ticket_id: int,
    req: app_mod.ApprovalDecisionRequest,
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    ticket = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if getattr(user, "username", "") != app_mod.ADMIN_USERNAME and ticket.username != user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bool(ticket.requires_approval) or bool(ticket.approved):
        raise HTTPException(status_code=400, detail="No pending approval for this ticket")

    log = (
        db.query(app_mod.ActionLog)
        .filter(app_mod.ActionLog.ticket_id == ticket.id, app_mod.ActionLog.requires_approval == 1, app_mod.ActionLog.approved == 0)
        .order_by(app_mod.ActionLog.id.desc())
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Pending approval log not found")

    rejection_note = str(req.internal_note or "Rejected by operator before execution.").strip()
    ticket.updated_at = app_mod._now_iso()
    ticket.status = app_mod._safe_status("escalated")
    ticket.queue = app_mod._safe_queue("escalated")
    ticket.requires_approval = 0
    ticket.approved = 0
    ticket.final_reply = "I’ve held this case for manual follow-up instead of executing the prepared action."
    app_mod.append_ticket_internal_note(ticket, rejection_note)
    app_mod.append_ticket_internal_note(ticket, f"Rejected by {user.username} at {app_mod._now_iso()}")

    log.status = "rejected"
    log.reason = rejection_note[:500]
    log.requires_approval = 0
    log.approved = 0

    db.commit()
    db.refresh(ticket)
    db.refresh(log)

    response = app_mod.build_ticket_response_payload(ticket, log, db=db)
    response["message"] = f"Ticket {ticket.id} rejected"
    try:
        pa = str(log.action or ticket.action or "none")
        pam = round(float(log.amount or ticket.amount or 0), 2)
        audit = app_mod.build_audit_summary_payload(
            proposed_action={
                "action": pa,
                "amount": pam,
                "reason": str(log.reason or "") or "Policy-sensitive motion",
                "requires_approval": True,
            },
            executed={
                "action": "review",
                "amount": 0.0,
                "tool_status": "rejected",
                "tool_result": {"status": "rejected"},
            },
            outcome_key=None,
            human_approved=False,
            issue_type=str(ticket.issue_type or "general_support"),
        )
        audit["approval"] = {"required": True, "human_confirmed": False}
        prop_l = str((audit.get("proposed") or {}).get("label") or "")
        rat = str(audit.get("rationale") or "")
        audit["trace"] = [
            f"Proposed: {prop_l}" if prop_l else f"Proposed: {pa}",
            f"Why: {rat}",
            "Approval: Operator declined — prepared motion not executed.",
            "Execution: Stopped — case left for manual follow-up.",
            "Accountability: Rejection recorded in workspace audit trail.",
        ]
        response["audit_summary"] = audit
    except Exception:
        pass
    return response


@router.get("/operator/mode")
def read_operator_mode(
    admin: app_mod.User = Depends(app_mod.require_admin),
    db: Session = Depends(app_mod.get_db),
):
    return {"mode": app_mod.get_operator_mode(db)}


@router.post("/operator/mode")
def update_operator_mode(
    req: app_mod.OperatorModeRequest,
    admin: app_mod.User = Depends(app_mod.require_admin),
    db: Session = Depends(app_mod.get_db),
):
    mode = app_mod.set_operator_mode(db, req.mode, by=admin.username)
    return {"mode": mode}


@router.post("/support")
def support(
    req: app_mod.SupportRequest,
    user: app_mod.User = Depends(app_mod.get_current_user),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    guest_client_id = app_mod.normalize_guest_client_id(x_guest_client)
    try:
        return app_mod.run_support(req, user, guest_client_id=guest_client_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "support_failed username=%s",
            getattr(user, "username", "") or "?",
        )
        raise


@router.post("/support/stream")
async def support_stream(
    req: app_mod.SupportRequest,
    authorization: str | None = Header(None),
    x_guest_client: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    username = app_mod.get_current_username_from_header(authorization)
    guest_client_id = app_mod.normalize_guest_client_id(x_guest_client)

    async def generator() -> AsyncIterator[str]:
        # Stream visible progress immediately so the UI does not sit on a blank loader
        # while the support pipeline is still computing the result.
        initial_steps = [
            {"stage": "reviewing", "label": "Reviewing request"},
            {"stage": "routing", "label": "Choosing next step"},
        ]
        for item in initial_steps:
            yield app_mod.sse_event("status", item)
            await asyncio.sleep(app_mod.STATUS_STEP_DELAY)

        try:
            result = await asyncio.wait_for(
                run_in_threadpool(app_mod.run_support_for_username, req, username, guest_client_id),
                timeout=28.0,
            )
        except HTTPException as he:
            detail = he.detail
            if isinstance(detail, dict):
                if he.status_code == 503:
                    app_mod._log_throttled_db_issue("support_ticket_persist", he)
                msg = str(detail.get("message") or detail.get("code") or "Request could not be completed.")
                code = str(detail.get("code") or "")
                if code == "preview_exhausted":
                    tool_st = "preview_blocked"
                    mode_val = "preview_blocked"
                elif he.status_code == 503:
                    tool_st = "db_unavailable"
                    mode_val = "db_unavailable"
                else:
                    tool_st = "blocked"
                    mode_val = "error"
                reason_key = code or ("db_unavailable" if he.status_code == 503 else "request_blocked")
                fallback = {
                    **detail,
                    "reply": msg,
                    "final": msg,
                    "response": msg,
                    "action": "review",
                    "amount": 0,
                    "reason": reason_key,
                    "issue_type": "general_support",
                    "order_status": "unknown",
                    "tool_status": tool_st,
                    "tool_result": {"status": tool_st, "code": code or None},
                    "impact": {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False},
                    "decision": {
                        "action": "review",
                        "queue": "escalated",
                        "priority": "high",
                        "risk_level": "medium",
                        "requires_approval": False,
                        "status": "waiting",
                    },
                    "execution": {
                        "action": "review",
                        "amount": 0,
                        "status": tool_st,
                        "auto_resolved": False,
                        "requires_approval": False,
                    },
                    "meta": {"operator_mode": "balanced"},
                    "triage": {},
                    "history": {},
                    "mode": mode_val,
                    "confidence": 0.0,
                    "quality": 0.0,
                }
            else:
                msg = str(detail) if detail else "Request could not be completed."
                if he.status_code == 503:
                    app_mod._log_throttled_db_issue("support_ticket_persist", he)
                fallback = {
                    "reply": msg,
                    "final": msg,
                    "response": msg,
                    "action": "review",
                    "amount": 0,
                    "reason": "db_unavailable",
                    "issue_type": "general_support",
                    "order_status": "unknown",
                    "tool_status": "db_unavailable",
                    "tool_result": {"status": "db_unavailable"},
                    "impact": {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False},
                    "decision": {
                        "action": "review",
                        "queue": "escalated",
                        "priority": "high",
                        "risk_level": "medium",
                        "requires_approval": False,
                        "status": "waiting",
                    },
                    "execution": {
                        "action": "review",
                        "amount": 0,
                        "status": "db_unavailable",
                        "auto_resolved": False,
                        "requires_approval": False,
                    },
                    "meta": {"operator_mode": "balanced"},
                    "triage": {},
                    "history": {},
                    "mode": "db_unavailable",
                    "confidence": 0.0,
                    "quality": 0.0,
                }
            label = (
                "Preview limit reached"
                if he.status_code == 402
                else ("Service unavailable" if he.status_code == 503 else "Could not complete request")
            )
            yield app_mod.sse_event("status", {"stage": "finalizing", "label": label})
            yield app_mod.sse_event("result", fallback)
            done_payload: dict[str, Any] = {"ok": False, "status": int(he.status_code)}
            if isinstance(he.detail, dict) and he.detail.get("code"):
                done_payload["code"] = he.detail.get("code")
            yield app_mod.sse_event("done", done_payload)
            return
        except asyncio.TimeoutError:
            logger.warning(
                "support_stream_timeout username=%s detail=wait_for_run_support_exceeded_28s "
                "typical_causes=slow_llm_or_threadpool_queue_db_pool_wait",
                username or "?",
            )
            fallback = {
                "reply": "I’m still processing this request. Please try again in a moment or send it once more and I’ll re-run the support flow.",
                "final": "I’m still processing this request. Please try again in a moment or send it once more and I’ll re-run the support flow.",
                "response": "I’m still processing this request. Please try again in a moment or send it once more and I’ll re-run the support flow.",
                "action": "review",
                "amount": 0,
                "reason": "stream_timeout",
                "issue_type": "general_support",
                "order_status": "unknown",
                "tool_status": "timeout",
                "tool_result": {"status": "timeout"},
                "impact": {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False},
                "decision": {"action": "review", "queue": "escalated", "priority": "high", "risk_level": "medium", "requires_approval": False, "status": "waiting"},
                "execution": {"action": "review", "amount": 0, "status": "timeout", "auto_resolved": False, "requires_approval": False},
                "meta": {"operator_mode": "balanced"},
                "triage": {},
                "history": {},
                "mode": "timeout",
                "confidence": 0.0,
                "quality": 0.0,
            }
            yield app_mod.sse_event("status", {"stage": "finalizing", "label": "Support run timed out"})
            yield app_mod.sse_event("result", fallback)
            yield app_mod.sse_event("done", {"ok": False, "timeout": True})
            return
        except Exception:
            logger.exception("support_stream_error username=%s", username or "?")
            fallback = {
                "reply": "I hit a temporary issue while processing this request. Please send it again and I’ll retry cleanly.",
                "final": "I hit a temporary issue while processing this request. Please send it again and I’ll retry cleanly.",
                "response": "I hit a temporary issue while processing this request. Please send it again and I’ll retry cleanly.",
                "action": "review",
                "amount": 0,
                "reason": "stream_error",
                "issue_type": "general_support",
                "order_status": "unknown",
                "tool_status": "error",
                "tool_result": {"status": "error"},
                "impact": {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False},
                "decision": {"action": "review", "queue": "escalated", "priority": "high", "risk_level": "medium", "requires_approval": False, "status": "waiting"},
                "execution": {"action": "review", "amount": 0, "status": "error", "auto_resolved": False, "requires_approval": False},
                "meta": {"operator_mode": "balanced"},
                "triage": {},
                "history": {},
                "mode": "error",
                "confidence": 0.0,
                "quality": 0.0,
            }
            yield app_mod.sse_event("status", {"stage": "finalizing", "label": "Support run failed"})
            yield app_mod.sse_event("result", fallback)
            yield app_mod.sse_event("done", {"ok": False})
            return

        for item in app_mod.build_status_sequence(result):
            stage = str(item.get("stage", "") or "")
            if stage in {"reviewing", "routing"}:
                continue
            yield app_mod.sse_event("status", item)
            await asyncio.sleep(app_mod.STATUS_STEP_DELAY)

        for part in app_mod.chunk_text(result.get("reply", ""), app_mod.STREAM_CHUNK_SIZE):
            yield app_mod.sse_event("chunk", {"text": part})
            await asyncio.sleep(app_mod.STREAM_CHUNK_DELAY)

        yield app_mod.sse_event("result", result)
        usage_warn = _stream_usage_warning_payload(username)
        if usage_warn:
            yield app_mod.sse_event("usage_warning", usage_warn)
        yield app_mod.sse_event("done", {"ok": True})

    return app_mod.StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
