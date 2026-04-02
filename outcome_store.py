"""
outcome_store.py — Real action outcome logging.

Tracks what actually happened after an action was executed or approved.
This is the source of truth for the learning system.

The problem with the previous system: learning.py called _score_outcome()
on the executed dict returned by execute_action() — which was self-reported
by the same agent that proposed the action.  Real outcomes (did the Shopify
refund process?  did the customer reply positively?  was there a chargeback?)
never fed back into rule reinforcement.

This module fixes that.  Every action execution and every human approval
writes a row here.  learning.py reads real outcomes from this table instead
of the self-reported executed dict.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, func

from db import Base, SessionLocal, engine, init_db


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class ActionOutcomeLog(Base):
    __tablename__ = "action_outcome_log"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    outcome_key        = Column(String(64), nullable=False, index=True)
    user_id            = Column(String(120), nullable=False, index=True)
    action             = Column(String(32), nullable=False, default="none")
    amount             = Column(Float, nullable=False, default=0.0)
    issue_type         = Column(String(64), nullable=False, default="general_support")
    success            = Column(Integer, nullable=False, default=0)   # 1=success 0=fail
    tool_status        = Column(String(64), nullable=False, default="unknown")
    auto_resolved      = Column(Integer, nullable=False, default=0)   # 1=fully automatic
    approved_by_human  = Column(Integer, nullable=False, default=0)   # 1=operator approved
    refund_reversed    = Column(Integer, nullable=False, default=0)   # future: chargeback signal
    dispute_filed      = Column(Integer, nullable=False, default=0)   # future: dispute signal
    tool_response_json = Column(Text, nullable=False, default="{}")
    created_at         = Column(String(32), nullable=False)
    updated_at         = Column(String(32), nullable=False)


init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SUCCESS_STATUSES = {"success", "credit_issued", "approved", "refunded"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_outcome(
    outcome_key: str,
    user_id: str,
    action: str,
    amount: float,
    issue_type: str,
    tool_result: dict[str, Any],
    auto_resolved: bool = True,
    approved_by_human: bool = False,
) -> dict[str, Any]:
    """
    Log the real outcome of an executed action.

    Call immediately after execute_action() returns.  outcome_key should be the
    idempotency key (or ticket_id as fallback) so learning.py can look it up.
    """
    tool_status = str(tool_result.get("status", "unknown") or "unknown")
    success     = 1 if tool_status in _SUCCESS_STATUSES else 0
    now         = _now_iso()

    db = SessionLocal()
    try:
        row = ActionOutcomeLog(
            outcome_key=str(outcome_key or "")[:64],
            user_id=str(user_id or "")[:120],
            action=str(action or "none")[:32],
            amount=round(float(amount or 0), 2),
            issue_type=str(issue_type or "general_support")[:64],
            success=success,
            tool_status=tool_status[:64],
            auto_resolved=int(auto_resolved),
            approved_by_human=int(approved_by_human),
            refund_reversed=0,
            dispute_filed=0,
            tool_response_json=json.dumps(tool_result, ensure_ascii=False)[:4000],
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id":          row.id,
            "outcome_key": row.outcome_key,
            "success":     bool(success),
            "tool_status": tool_status,
        }
    except Exception:
        db.rollback()
        return {}
    finally:
        db.close()


def get_outcome(outcome_key: str) -> dict[str, Any] | None:
    """Retrieve the real outcome for a given key. Returns None if not found."""
    db = SessionLocal()
    try:
        row = (
            db.query(ActionOutcomeLog)
            .filter(ActionOutcomeLog.outcome_key == str(outcome_key or "")[:64])
            .order_by(ActionOutcomeLog.id.desc())
            .first()
        )
        if not row:
            return None
        return {
            "id":               row.id,
            "outcome_key":      row.outcome_key,
            "action":           row.action,
            "amount":           row.amount,
            "success":          bool(row.success),
            "tool_status":      row.tool_status,
            "auto_resolved":    bool(row.auto_resolved),
            "approved_by_human": bool(row.approved_by_human),
            "refund_reversed":  bool(row.refund_reversed),
            "dispute_filed":    bool(row.dispute_filed),
            "created_at":       row.created_at,
        }
    finally:
        db.close()


def mark_reversed(outcome_key: str) -> bool:
    """Mark an outcome as reversed (chargeback/dispute). Future-ready for webhook signals."""
    db = SessionLocal()
    try:
        row = db.query(ActionOutcomeLog).filter(
            ActionOutcomeLog.outcome_key == str(outcome_key or "")[:64]
        ).first()
        if not row:
            return False
        row.refund_reversed = 1
        row.updated_at = _now_iso()
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_outcome_stats() -> dict[str, Any]:
    """Aggregate real outcome stats. Used by the /metrics endpoint."""
    db = SessionLocal()
    try:
        total = db.query(ActionOutcomeLog).count()
        if not total:
            return {
                "total":               0,
                "success_rate":        0.0,
                "auto_resolution_rate": 0.0,
                "human_approved":      0,
                "reversed":            0,
                "money_moved":         0.0,
            }

        successes      = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.success == 1).count()
        auto           = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.auto_resolved == 1).count()
        human_approved = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.approved_by_human == 1).count()
        reversed_count = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.refund_reversed == 1).count()
        money_moved    = db.query(func.sum(ActionOutcomeLog.amount)).filter(
            ActionOutcomeLog.action.in_(["refund", "credit"]),
            ActionOutcomeLog.success == 1,
        ).scalar() or 0.0

        return {
            "total":               total,
            "successes":           successes,
            "success_rate":        round(successes / max(1, total) * 100, 1),
            "auto_resolved":       auto,
            "auto_resolution_rate": round(auto / max(1, total) * 100, 1),
            "human_approved":      human_approved,
            "reversed":            reversed_count,
            "money_moved":         round(float(money_moved), 2),
        }
    finally:
        db.close()
