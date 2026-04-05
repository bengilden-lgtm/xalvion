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

from sqlalchemy import inspect, text

from db import Base, SessionLocal, engine


_outcome_stats_cache: dict[str, Any] = {}
_outcome_stats_cache_ts: float = 0.0
_OUTCOME_STATS_TTL: float = 30.0


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
    ticket_reopened    = Column(Integer, nullable=False, default=0)
    crm_closed         = Column(Integer, nullable=False, default=0)
    tool_response_json = Column(Text, nullable=False, default="{}")
    created_at         = Column(String(32), nullable=False)
    updated_at         = Column(String(32), nullable=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_response_json(tool_result: dict[str, Any]) -> str:
    try:
        return json.dumps(tool_result, ensure_ascii=False, default=str)[:4000]
    except Exception:
        return "{}"


def ensure_outcome_log_columns() -> None:
    """Lazy migration for action_outcome_log — same pattern as app.ensure_user_columns."""
    try:
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("action_outcome_log")}
        additions: list[str] = []
        if "ticket_reopened" not in cols:
            additions.append(
                "ALTER TABLE action_outcome_log ADD COLUMN ticket_reopened INTEGER DEFAULT 0 NOT NULL"
            )
        if "crm_closed" not in cols:
            additions.append(
                "ALTER TABLE action_outcome_log ADD COLUMN crm_closed INTEGER DEFAULT 0 NOT NULL"
            )
        if additions:
            with engine.begin() as conn:
                for stmt in additions:
                    conn.execute(text(stmt))
    except Exception:
        pass


def ensure_outcome_columns() -> None:
    """Alias for lazy outcome table migration (startup hook name)."""
    ensure_outcome_log_columns()


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
            ticket_reopened=0,
            crm_closed=0,
            tool_response_json=_tool_response_json(tool_result if isinstance(tool_result, dict) else {"raw": tool_result}),
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


def _outcome_orm_to_dict(row: ActionOutcomeLog) -> dict[str, Any]:
    return {
        "success":          bool(row.success),
        "auto_resolved":    bool(row.auto_resolved),
        "approved_by_human": bool(row.approved_by_human),
        "refund_reversed":  bool(row.refund_reversed),
        "dispute_filed":    bool(row.dispute_filed),
        "ticket_reopened":  bool(getattr(row, "ticket_reopened", 0)),
        "crm_closed":       bool(getattr(row, "crm_closed", 0)),
    }


def normalize_business_outcome(row_dict: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalized business semantics for an outcome row (dict from get_outcome or ORM-shaped dict).
    Additive helper — does not replace compute_outcome_impact.
    """
    if not row_dict:
        return {
            "resolution_class": "unknown",
            "financial_motion": False,
            "stability": "unknown",
            "risk_flags": [],
        }

    success = bool(row_dict.get("success"))
    auto_r = bool(row_dict.get("auto_resolved"))
    reopened = bool(row_dict.get("ticket_reopened"))
    reversed_f = bool(row_dict.get("refund_reversed"))
    dispute = bool(row_dict.get("dispute_filed"))
    action = str(row_dict.get("action", "none") or "none")
    amt = float(row_dict.get("amount", 0) or 0)

    risk_flags: list[str] = []
    if reversed_f:
        risk_flags.append("refund_reversed")
    if dispute:
        risk_flags.append("dispute_filed")
    if reopened:
        risk_flags.append("ticket_reopened")

    if reversed_f or dispute:
        stability = "fragile"
    elif reopened:
        stability = "unstable"
    elif success and auto_r:
        stability = "stable_auto"
    elif success:
        stability = "stable"
    else:
        stability = "failed"

    if success and auto_r and not reopened and not reversed_f and not dispute:
        resolution_class = "auto_success"
    elif success:
        resolution_class = "assisted_success"
    else:
        resolution_class = "failed"

    return {
        "resolution_class": resolution_class,
        "financial_motion": action in {"refund", "credit", "charge"} and amt > 0,
        "stability": stability,
        "risk_flags": risk_flags,
        "action_family": action,
    }


def public_outcome_digest_for_audit(row_dict: dict[str, Any] | None) -> dict[str, Any]:
    """
    Compact, operator-safe outcome view for trust traces.
    Excludes raw tool JSON and internal identifiers beyond correlation key.
    """
    if not row_dict:
        return {"known": False, "summary": None, "tier": None, "success": None}

    summary_ui = build_outcome_summary_for_ui(row_dict)
    headline = str(summary_ui.get("headline") or "").strip() or "Outcome on file"
    tier = str(summary_ui.get("tier") or "neutral")

    return {
        "known": True,
        "summary": headline[:280],
        "tier": tier,
        "success": bool(row_dict.get("success")),
    }


def merge_audit_outcome_digest(audit: dict[str, Any] | None, outcome_key: str | None) -> dict[str, Any] | None:
    """
    Attach verified outcome headline to an audit_summary dict (copy — does not mutate input).
    """
    if audit is None and not (outcome_key or "").strip():
        return None

    base: dict[str, Any] = dict(audit) if audit is not None else {"version": 1, "trace": []}
    key = str(outcome_key or "").strip() or None
    if not key:
        base.setdefault(
            "outcome",
            {"known": False, "summary": None, "tier": None, "success": None},
        )
        return base

    try:
        row = get_outcome(key)
    except Exception:
        row = None
    digest = public_outcome_digest_for_audit(row)
    base["outcome"] = digest
    base["outcome_key"] = key
    if digest.get("known") and digest.get("summary"):
        trace = list(base.get("trace") or [])
        if trace:
            trace = trace + [f"Recorded outcome: {digest['summary']}"]
        else:
            trace = [f"Recorded outcome: {digest['summary']}"]
        base["trace"] = trace
    return base


def build_outcome_summary_for_ui(row_dict: dict[str, Any] | None) -> dict[str, Any]:
    """
    Compact card-shaped summary for frontends. Backward compatible: only adds structure;
    existing callers of get_outcome / log_outcome unchanged.
    """
    if not row_dict:
        return {
            "headline": "No outcome recorded",
            "tier": "neutral",
            "score": 0.5,
            "badges": [],
            "money": {"refund": 0.0, "credit": 0.0},
            "flags": normalize_business_outcome(None),
        }

    imp = compute_outcome_impact(row_dict)
    norm = normalize_business_outcome(row_dict)
    action = str(row_dict.get("action", "none") or "none")
    amt = round(float(row_dict.get("amount", 0) or 0), 2)

    headline = f"{action.replace('_', ' ').title()} · {imp['impact_label']} outcome"
    if action == "refund" and amt > 0:
        headline = f"Refund ${amt:.0f} · {imp['impact_label']}"
    elif action == "credit" and amt > 0:
        headline = f"Credit ${amt:.0f} · {imp['impact_label']}"

    badges = [imp["impact_label"], norm["stability"], norm["resolution_class"]]
    money = {"refund": amt if action == "refund" else 0.0, "credit": amt if action == "credit" else 0.0}

    return {
        "outcome_key": row_dict.get("outcome_key"),
        "headline": headline,
        "tier": imp["impact_label"],
        "score": imp["impact_score"],
        "badges": [b for b in badges if b and b != "unknown"],
        "money": money,
        "flags": norm,
        "components": imp.get("component_scores") or {},
    }


def compute_outcome_impact(row_dict: dict[str, Any] | None) -> dict[str, Any]:
    """
    Authoritative normalized impact for an outcome record (dict from get_outcome()
    or equivalent booleans).

    If refund_reversed is set, success / auto / human completion bonuses do not
    count toward impact (the favorable outcome did not hold).

    Never raises — returns a neutral default on any error.
    """
    try:
        if not row_dict:
            return {
                "impact_score":     0.5,
                "impact_label":     "neutral",
                "component_scores": {},
            }

        reversed_flag = bool(row_dict.get("refund_reversed"))
        success_val = (
            0.0
            if reversed_flag
            else (2.5 if row_dict.get("success") else 0.0)
        )
        auto_val = (
            0.0
            if reversed_flag
            else (1.0 if row_dict.get("auto_resolved") else 0.0)
        )
        human_val = (
            0.0
            if reversed_flag
            else (0.5 if row_dict.get("approved_by_human") else 0.0)
        )
        reversal_val = -3.0 if row_dict.get("refund_reversed") else 0.0
        dispute_val = -2.0 if row_dict.get("dispute_filed") else 0.0
        reopen_val = -1.5 if row_dict.get("ticket_reopened") else 0.0
        crm_val = 0.8 if row_dict.get("crm_closed") else 0.0

        components = {
            "success":          success_val,
            "auto_resolved":    auto_val,
            "human_approved":   human_val,
            "reversal_penalty": reversal_val,
            "dispute_penalty":  dispute_val,
            "reopen_penalty":   reopen_val,
            "crm_bonus":        crm_val,
        }

        raw = sum(components.values())
        normalized = (raw + 5.5) / 10.3
        normalized = round(max(0.0, min(1.0, normalized)), 4)

        if normalized >= 0.80:
            label = "excellent"
        elif normalized >= 0.58:
            label = "good"
        elif normalized >= 0.38:
            label = "neutral"
        else:
            label = "bad"

        return {
            "impact_score":     normalized,
            "impact_label":     label,
            "component_scores": components,
        }
    except Exception:
        return {
            "impact_score":     0.5,
            "impact_label":     "neutral",
            "component_scores": {},
        }


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
            "ticket_reopened":  bool(getattr(row, "ticket_reopened", 0)),
            "crm_closed":       bool(getattr(row, "crm_closed", 0)),
            "created_at":       row.created_at,
        }
    finally:
        db.close()


def get_impact_for_key(outcome_key: str) -> dict[str, Any] | None:
    row = get_outcome(outcome_key)
    if not row:
        return None
    return compute_outcome_impact(row)


def compute_outcome_quality(row: ActionOutcomeLog) -> float:
    score = 0.0
    if int(row.success or 0):
        score += 2.5
    if int(row.auto_resolved or 0):
        score += 1.0
    if int(row.approved_by_human or 0):
        score += 0.5
    if int(row.refund_reversed or 0):
        score -= 3.0
    if int(row.dispute_filed or 0):
        score -= 2.0
    if int(getattr(row, "ticket_reopened", 0) or 0):
        score -= 1.5
    if int(getattr(row, "crm_closed", 0) or 0):
        score += 0.8
    score = max(0.0, min(5.0, score))
    return round(score, 4)


def get_outcome_quality_for_key(outcome_key: str) -> float | None:
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
        return compute_outcome_quality(row)
    finally:
        db.close()


def mark_ticket_reopened(outcome_key: str) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(ActionOutcomeLog)
            .filter(ActionOutcomeLog.outcome_key == str(outcome_key or "")[:64])
            .order_by(ActionOutcomeLog.id.desc())
            .first()
        )
        if not row:
            return False
        row.ticket_reopened = 1
        row.updated_at = _now_iso()
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def mark_crm_closed(outcome_key: str) -> bool:
    db = SessionLocal()
    try:
        row = (
            db.query(ActionOutcomeLog)
            .filter(ActionOutcomeLog.outcome_key == str(outcome_key or "")[:64])
            .order_by(ActionOutcomeLog.id.desc())
            .first()
        )
        if not row:
            return False
        row.crm_closed = 1
        row.updated_at = _now_iso()
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
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
    import time as _time

    global _outcome_stats_cache, _outcome_stats_cache_ts

    now = _time.time()
    if _outcome_stats_cache and (now - _outcome_stats_cache_ts) < _OUTCOME_STATS_TTL:
        return dict(_outcome_stats_cache)

    db = SessionLocal()
    try:
        avg_impact_score = 0.5
        excellent_rate = 0.0
        bad_rate = 0.0
        good_excellent_outcome_rate = 0.0
        try:
            sample_rows = (
                db.query(ActionOutcomeLog)
                .order_by(ActionOutcomeLog.id.desc())
                .limit(500)
                .all()
            )
            if sample_rows:
                impacts = [compute_outcome_impact(_outcome_orm_to_dict(r)) for r in sample_rows]
                n = len(impacts)
                avg_impact_score = round(
                    sum(i["impact_score"] for i in impacts) / max(1, n), 4
                )
                excellent_rate = round(
                    sum(1 for i in impacts if i["impact_label"] == "excellent") / max(1, n) * 100, 2
                )
                bad_rate = round(
                    sum(1 for i in impacts if i["impact_label"] == "bad") / max(1, n) * 100, 2
                )
                good_excellent_outcome_rate = round(
                    sum(1 for i in impacts if i["impact_label"] in {"good", "excellent"}) / max(1, n) * 100,
                    2,
                )
            else:
                good_excellent_outcome_rate = 0.0
        except Exception:
            avg_impact_score, excellent_rate, bad_rate = 0.5, 0.0, 0.0
            good_excellent_outcome_rate = 0.0

        total = db.query(ActionOutcomeLog).count()
        if not total:
            result = {
                "total":               0,
                "success_rate":        0.0,
                "auto_resolution_rate": 0.0,
                "human_approved":      0,
                "reversed":            0,
                "money_moved":         0.0,
                "avg_outcome_quality": 0.0,
                "reopened_rate":       0.0,
                "crm_close_rate":      0.0,
                "avg_impact_score":    0.5,
                "excellent_rate":      0.0,
                "bad_rate":            0.0,
                "good_excellent_outcome_rate": 0.0,
            }
            _outcome_stats_cache.clear()
            _outcome_stats_cache.update(result)
            _outcome_stats_cache_ts = now
            return result

        successes      = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.success == 1).count()
        auto           = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.auto_resolved == 1).count()
        human_approved = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.approved_by_human == 1).count()
        reversed_count = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.refund_reversed == 1).count()
        reopened_n     = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.ticket_reopened == 1).count()
        crm_closed_n   = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.crm_closed == 1).count()
        money_moved    = db.query(func.sum(ActionOutcomeLog.amount)).filter(
            ActionOutcomeLog.action.in_(["refund", "credit"]),
            ActionOutcomeLog.success == 1,
        ).scalar() or 0.0

        success_rows = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.success == 1).all()
        qualities = [compute_outcome_quality(r) for r in success_rows]
        avg_q = round(sum(qualities) / max(1, len(qualities)), 4) if qualities else 0.0

        result = {
            "total":               total,
            "successes":           successes,
            "success_rate":        round(successes / max(1, total) * 100, 1),
            "auto_resolved":       auto,
            "auto_resolution_rate": round(auto / max(1, total) * 100, 1),
            "human_approved":      human_approved,
            "reversed":            reversed_count,
            "money_moved":         round(float(money_moved), 2),
            "avg_outcome_quality": avg_q,
            "reopened_rate":       round(reopened_n / max(1, total) * 100, 2),
            "crm_close_rate":      round(crm_closed_n / max(1, total) * 100, 2),
            "avg_impact_score":    avg_impact_score,
            "excellent_rate":      excellent_rate,
            "bad_rate":            bad_rate,
            "good_excellent_outcome_rate": good_excellent_outcome_rate,
        }
        _outcome_stats_cache.clear()
        _outcome_stats_cache.update(result)
        _outcome_stats_cache_ts = now
        return result
    finally:
        db.close()
