from __future__ import annotations

import logging
import threading
import time as _time_mod
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case as _case, func as _func
from sqlalchemy.orm import Session

import app as app_mod

router = APIRouter(tags=["dashboard"])

logger = logging.getLogger("xalvion.api")

_dashboard_cache_lock = threading.Lock()


def _dashboard_summary_fallback(user: app_mod.User, db: Session, file_metrics: dict[str, Any]) -> dict[str, Any]:
    """Same JSON shape as dashboard_summary when DB aggregations fail."""
    usage_summary = app_mod.get_usage_summary(user)
    public_tier = app_mod.get_public_plan_name(user)
    pc = app_mod.get_plan_config(public_tier)
    operator_mode = "balanced"
    try:
        operator_mode = app_mod.get_operator_mode(db)
    except Exception:
        pass
    return {
        "total_interactions": int(file_metrics.get("total_interactions", 0) or 0),
        "avg_confidence": float(file_metrics.get("avg_confidence", 0) or 0),
        "avg_quality": float(file_metrics.get("avg_quality", 0) or 0),
        "total_tickets": 0,
        "auto_resolved": 0,
        "escalated": 0,
        "failed": 0,
        "high_churn_risk": 0,
        "pending_approvals": 0,
        "approved_actions": 0,
        "auto_resolution_rate": 0.0,
        "escalation_rate": 0.0,
        "refund_total": 0.0,
        "credit_total": 0.0,
        "money_saved": 0.0,
        "actions": 0,
        "by_queue": {},
        "by_priority": {},
        "by_risk": {},
        "by_status": {},
        "your_usage": usage_summary["usage"],
        "your_tier": public_tier,
        "your_limit": pc["monthly_limit"],
        "remaining": usage_summary["remaining"],
        "dashboard_access": pc["dashboard_access"],
        "priority_routing": pc["priority_routing"],
        "operator_mode": operator_mode,
        "total_users": 0,
        "pro_users": 0,
        "elite_users": 0,
        "outcome_quality": 0.0,
        "reopened_rate": 0.0,
        "crm_close_rate": 0.0,
        "value_generated": {
            "money_saved":        0.0,
            "time_saved_minutes": 0,
            "actions_taken":      0,
        },
    }


@router.get("/dashboard/summary")
def dashboard_summary(
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    file_metrics = {**app_mod._METRICS_FALLBACK, **(app_mod.get_metrics() or {})}
    outcome_stats: dict[str, Any] = {}
    try:
        outcome_stats = app_mod.get_outcome_stats()
    except Exception:
        outcome_stats = {}

    _now = _time_mod.time()
    if app_mod._dashboard_cache and (_now - app_mod._dashboard_cache_ts) < app_mod._DASHBOARD_TTL:
        cached = dict(app_mod._dashboard_cache)
        usage_summary = app_mod.get_usage_summary(user)
        public_tier = app_mod.get_public_plan_name(user)
        pc = app_mod.get_plan_config(public_tier)
        cached.update({
            "your_usage": usage_summary["usage"],
            "your_tier": public_tier,
            "your_limit": pc["monthly_limit"],
            "remaining": usage_summary["remaining"],
        })
        ms = float(cached.get("money_saved", 0) or 0)
        act = int(cached.get("actions", 0) or 0)
        cached["value_generated"] = {
            "money_saved": round(ms, 2),
            "time_saved_minutes": int(act * 6),
            "actions_taken": act,
        }
        try:
            cached["operator_mode"] = app_mod.get_operator_mode(db)
        except Exception:
            pass
        return cached

    try:
        _tkt = db.query(
            _func.count(app_mod.Ticket.id).label("total"),
            _func.count(_case((app_mod.Ticket.status == "resolved", 1), else_=None)).label("resolved"),
            _func.count(_case((app_mod.Ticket.status.in_(["waiting", "escalated"]), 1), else_=None)).label("escalated"),
            _func.count(_case((app_mod.Ticket.status == "failed", 1), else_=None)).label("failed"),
            _func.count(_case((app_mod.Ticket.churn_risk >= 60, 1), else_=None)).label("high_risk"),
        ).one_or_none()

        if _tkt is None:
            total_tickets = auto_resolved = escalated = failed_count = high_risk = 0
        else:
            total_tickets = int(_tkt.total or 0)
            auto_resolved = int(_tkt.resolved or 0)
            escalated = int(_tkt.escalated or 0)
            failed_count = int(_tkt.failed or 0)
            high_risk = int(_tkt.high_risk or 0)

        pending_approvals = db.query(app_mod.ActionLog).filter(
            app_mod.ActionLog.requires_approval == 1,
            app_mod.ActionLog.approved == 0,
        ).count()

        _act = db.query(
            _func.coalesce(_func.sum(_case((app_mod.ActionLog.action == "refund", app_mod.ActionLog.amount), else_=0)), 0).label("refund_total"),
            _func.coalesce(_func.sum(_case((app_mod.ActionLog.action == "credit", app_mod.ActionLog.amount), else_=0)), 0).label("credit_total"),
            _func.count(_case((app_mod.ActionLog.action.in_(["refund", "credit"]), 1), else_=None)).label("actions_done"),
            _func.count(_case((app_mod.ActionLog.approved == 1, 1), else_=None)).label("approved_count"),
            _func.avg(_case((app_mod.ActionLog.confidence > 0, app_mod.ActionLog.confidence), else_=None)).label("avg_conf"),
            _func.avg(_case((app_mod.ActionLog.quality > 0, app_mod.ActionLog.quality), else_=None)).label("avg_qual"),
        ).one_or_none()

        if _act is None:
            refund_total = credit_total = 0.0
            actions_done = approved_count = 0
            db_avg_conf = db_avg_qual = 0.0
        else:
            refund_total = float(_act.refund_total or 0)
            credit_total = float(_act.credit_total or 0)
            actions_done = int(_act.actions_done or 0)
            approved_count = int(_act.approved_count or 0)
            db_avg_conf = float(_act.avg_conf or 0)
            db_avg_qual = float(_act.avg_qual or 0)

        avg_confidence = file_metrics.get("avg_confidence") or round(db_avg_conf, 4)
        avg_quality = file_metrics.get("avg_quality") or round(db_avg_qual, 4)

        queue_rows = db.query(app_mod.Ticket.queue, _func.count(app_mod.Ticket.id)).group_by(app_mod.Ticket.queue).all()
        prio_rows = db.query(app_mod.Ticket.priority, _func.count(app_mod.Ticket.id)).group_by(app_mod.Ticket.priority).all()
        risk_rows = db.query(app_mod.Ticket.risk_level, _func.count(app_mod.Ticket.id)).group_by(app_mod.Ticket.risk_level).all()
        status_rows = db.query(app_mod.Ticket.status, _func.count(app_mod.Ticket.id)).group_by(app_mod.Ticket.status).all()

        by_queue = {app_mod._safe_queue(q or "new"): int(c) for q, c in queue_rows}
        by_priority = {app_mod._safe_priority(p or "medium"): int(c) for p, c in prio_rows}
        by_risk = {app_mod._safe_risk(r or "medium"): int(c) for r, c in risk_rows}
        by_status = {app_mod._safe_status(s or "new"): int(c) for s, c in status_rows}

        usage_summary = app_mod.get_usage_summary(user)
        public_tier = app_mod.get_public_plan_name(user)

        result = {
            "total_interactions": file_metrics.get("total_interactions", 0),
            "avg_confidence": avg_confidence,
            "avg_quality": avg_quality,
            "total_tickets": total_tickets,
            "auto_resolved": auto_resolved,
            "escalated": escalated,
            "failed": failed_count,
            "high_churn_risk": high_risk,
            "pending_approvals": pending_approvals,
            "approved_actions": approved_count,
            "auto_resolution_rate": round(auto_resolved / max(1, total_tickets) * 100, 2),
            "escalation_rate": round(escalated / max(1, total_tickets) * 100, 2),
            "refund_total": round(refund_total, 2),
            "credit_total": round(credit_total, 2),
            "money_saved": round(refund_total + credit_total, 2),
            "actions": actions_done,
            "by_queue": by_queue,
            "by_priority": by_priority,
            "by_risk": by_risk,
            "by_status": by_status,
            "your_usage": usage_summary["usage"],
            "your_tier": public_tier,
            "your_limit": app_mod.get_plan_config(public_tier)["monthly_limit"],
            "remaining": usage_summary["remaining"],
            "dashboard_access": app_mod.get_plan_config(public_tier)["dashboard_access"],
            "priority_routing": app_mod.get_plan_config(public_tier)["priority_routing"],
            "operator_mode": app_mod.get_operator_mode(db),
            "total_users": db.query(app_mod.User).count(),
            "pro_users": db.query(app_mod.User).filter(app_mod.User.tier == "pro").count(),
            "elite_users": db.query(app_mod.User).filter(app_mod.User.tier == "elite").count(),
            "outcome_quality": float(outcome_stats.get("avg_outcome_quality", 0.0) or 0.0),
            "reopened_rate": float(outcome_stats.get("reopened_rate", 0.0) or 0.0),
            "crm_close_rate": float(outcome_stats.get("crm_close_rate", 0.0) or 0.0),
            "value_generated": {
                "money_saved":        round(refund_total + credit_total, 2),
                "time_saved_minutes": int(actions_done * 6),
                "actions_taken":      actions_done,
            },
        }
        # Cache is per-process; no effect under multi-worker deployments.
        with _dashboard_cache_lock:
            app_mod._dashboard_cache.clear()
            app_mod._dashboard_cache.update(result)
            app_mod._dashboard_cache_ts = _now
        return result
    except Exception as exc:
        app_mod._log_throttled_db_issue("GET /dashboard/summary", exc)
        return _dashboard_summary_fallback(user, db, file_metrics)
