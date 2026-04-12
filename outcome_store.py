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
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, func

from sqlalchemy import inspect, text

from db import Base, SessionLocal, engine

logger = logging.getLogger("xalvion.outcome_store")


# Outcome intelligence snapshot cache (UI-facing, compact)
_outcome_intel_cache: dict[str, Any] = {}
_outcome_intel_cache_ts: dict[str, float] = {}
_OUTCOME_INTEL_TTL: float = 15.0


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
        logger.warning("tool_response_json_serialize_failed", exc_info=True)
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
    except Exception as e:
        import logging
        logging.error("outcome_store_migration_failed: %s", str(e), exc_info=True)


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
    except Exception as exc:
        db.rollback()
        logger.error(
            "log_outcome_failed outcome_key=%s user_id=%s action=%s tool_status=%s detail=%s",
            str(outcome_key or "")[:64],
            str(user_id or "")[:120],
            str(action or "none")[:32],
            str(tool_status or "unknown")[:64],
            str(exc)[:500],
            exc_info=True,
        )
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
    except Exception as exc:
        db.rollback()
        logger.error(
            "mark_ticket_reopened_failed outcome_key=%s detail=%s",
            str(outcome_key or "")[:64],
            str(exc)[:500],
            exc_info=True,
        )
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
    except Exception as exc:
        db.rollback()
        logger.error(
            "mark_crm_closed_failed outcome_key=%s detail=%s",
            str(outcome_key or "")[:64],
            str(exc)[:500],
            exc_info=True,
        )
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
    except Exception as exc:
        db.rollback()
        logger.error(
            "mark_reversed_failed outcome_key=%s detail=%s",
            str(outcome_key or "")[:64],
            str(exc)[:500],
            exc_info=True,
        )
        return False
    finally:
        db.close()


def _empty_outcome_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "success_rate": 0.0,
        "auto_resolution_rate": 0.0,
        "human_approved": 0,
        "reversed": 0,
        "money_moved": 0.0,
        "avg_outcome_quality": 0.0,
        "reopened_rate": 0.0,
        "crm_close_rate": 0.0,
        "avg_impact_score": 0.5,
        "excellent_rate": 0.0,
        "bad_rate": 0.0,
        "good_excellent_outcome_rate": 0.0,
    }


def get_outcome_stats(user_id: str | None = None) -> dict[str, Any]:
    """Aggregate real outcome stats for a single workspace principal (username or guest client id).

    Callers must pass ``user_id``; without it we return zeros so we never leak cross-tenant aggregates.
    """
    uid = str(user_id or "").strip()[:120]
    if not uid:
        return _empty_outcome_stats()

    db = SessionLocal()
    try:
        scope = db.query(ActionOutcomeLog).filter(ActionOutcomeLog.user_id == uid)

        avg_impact_score = 0.5
        excellent_rate = 0.0
        bad_rate = 0.0
        good_excellent_outcome_rate = 0.0
        try:
            sample_rows = scope.order_by(ActionOutcomeLog.id.desc()).limit(500).all()
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
            logger.warning("get_outcome_stats_sample_impact_failed", exc_info=True)

        total = int(scope.count() or 0)
        if not total:
            return _empty_outcome_stats()

        successes = int(scope.filter(ActionOutcomeLog.success == 1).count() or 0)
        auto = int(scope.filter(ActionOutcomeLog.auto_resolved == 1).count() or 0)
        human_approved = int(scope.filter(ActionOutcomeLog.approved_by_human == 1).count() or 0)
        reversed_count = int(scope.filter(ActionOutcomeLog.refund_reversed == 1).count() or 0)
        reopened_n = int(scope.filter(ActionOutcomeLog.ticket_reopened == 1).count() or 0)
        crm_closed_n = int(scope.filter(ActionOutcomeLog.crm_closed == 1).count() or 0)
        money_moved = (
            db.query(func.sum(ActionOutcomeLog.amount))
            .filter(
                ActionOutcomeLog.user_id == uid,
                ActionOutcomeLog.action.in_(["refund", "credit"]),
                ActionOutcomeLog.success == 1,
            )
            .scalar()
            or 0.0
        )

        success_rows = scope.filter(ActionOutcomeLog.success == 1).all()
        qualities = [compute_outcome_quality(r) for r in success_rows]
        avg_q = round(sum(qualities) / max(1, len(qualities)), 4) if qualities else 0.0

        return {
            "total": total,
            "successes": successes,
            "success_rate": round(successes / max(1, total) * 100, 1),
            "auto_resolved": auto,
            "auto_resolution_rate": round(auto / max(1, total) * 100, 1),
            "human_approved": human_approved,
            "reversed": reversed_count,
            "money_moved": round(float(money_moved), 2),
            "avg_outcome_quality": avg_q,
            "reopened_rate": round(reopened_n / max(1, total) * 100, 2),
            "crm_close_rate": round(crm_closed_n / max(1, total) * 100, 2),
            "avg_impact_score": avg_impact_score,
            "excellent_rate": excellent_rate,
            "bad_rate": bad_rate,
            "good_excellent_outcome_rate": good_excellent_outcome_rate,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Outcome intelligence (additive UI surface)
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return default


def summarize_recent_outcomes(limit: int = 25, user_id: str | None = None) -> dict[str, Any]:
    """
    Compact aggregation over the most recent outcome rows.
    Additive helper; never raises; safe to call from summary endpoints.
    """
    lim = max(1, min(500, _safe_int(limit, 25)))
    uid = str(user_id or "").strip()[:120]
    db = SessionLocal()
    try:
        q = db.query(ActionOutcomeLog)
        if uid:
            q = q.filter(ActionOutcomeLog.user_id == uid)
        else:
            return {
                "excellent": 0,
                "good": 0,
                "neutral": 0,
                "bad": 0,
                "auto_success": 0,
                "assisted_success": 0,
                "failed": 0,
                "ticket_reopened": 0,
                "refund_reversed": 0,
                "dispute_filed": 0,
                "crm_closed": 0,
                "money_refunded": 0.0,
                "money_credited": 0.0,
            }
        rows = q.order_by(ActionOutcomeLog.id.desc()).limit(lim).all()
        if not rows:
            return {
                "excellent": 0,
                "good": 0,
                "neutral": 0,
                "bad": 0,
                "auto_success": 0,
                "assisted_success": 0,
                "failed": 0,
                "ticket_reopened": 0,
                "refund_reversed": 0,
                "dispute_filed": 0,
                "crm_closed": 0,
                "money_refunded": 0.0,
                "money_credited": 0.0,
            }

        counts = {
            "excellent": 0,
            "good": 0,
            "neutral": 0,
            "bad": 0,
            "auto_success": 0,
            "assisted_success": 0,
            "failed": 0,
            "ticket_reopened": 0,
            "refund_reversed": 0,
            "dispute_filed": 0,
            "crm_closed": 0,
            "money_refunded": 0.0,
            "money_credited": 0.0,
        }

        for r in rows:
            d = {
                "success": bool(r.success),
                "auto_resolved": bool(r.auto_resolved),
                "approved_by_human": bool(r.approved_by_human),
                "refund_reversed": bool(r.refund_reversed),
                "dispute_filed": bool(r.dispute_filed),
                "ticket_reopened": bool(getattr(r, "ticket_reopened", 0)),
                "crm_closed": bool(getattr(r, "crm_closed", 0)),
                "action": r.action,
                "amount": r.amount,
            }
            imp = compute_outcome_impact(d)
            tier = str(imp.get("impact_label") or "neutral")
            if tier in counts:
                counts[tier] += 1

            norm = normalize_business_outcome(d)
            rc = str(norm.get("resolution_class") or "unknown")
            if rc == "auto_success":
                counts["auto_success"] += 1
            elif rc == "assisted_success":
                counts["assisted_success"] += 1
            elif rc == "failed":
                counts["failed"] += 1

            if d["ticket_reopened"]:
                counts["ticket_reopened"] += 1
            if d["refund_reversed"]:
                counts["refund_reversed"] += 1
            if d["dispute_filed"]:
                counts["dispute_filed"] += 1
            if d["crm_closed"]:
                counts["crm_closed"] += 1

            action = str(d.get("action") or "none").lower()
            amt = round(_safe_float(d.get("amount"), 0.0), 2)
            if amt > 0 and d.get("success"):
                if action == "refund":
                    counts["money_refunded"] = round(float(counts["money_refunded"]) + amt, 2)
                elif action == "credit":
                    counts["money_credited"] = round(float(counts["money_credited"]) + amt, 2)

        return counts
    except Exception:
        return {
            "excellent": 0,
            "good": 0,
            "neutral": 0,
            "bad": 0,
            "auto_success": 0,
            "assisted_success": 0,
            "failed": 0,
            "ticket_reopened": 0,
            "refund_reversed": 0,
            "dispute_filed": 0,
            "crm_closed": 0,
            "money_refunded": 0.0,
            "money_credited": 0.0,
        }
    finally:
        db.close()


def latest_outcome_summary(user_id: str | None = None) -> dict[str, Any] | None:
    """
    Latest outcome row summarized for UI.
    Returns None if no rows exist; never raises.
    """
    uid = str(user_id or "").strip()[:120]
    if not uid:
        return None
    db = SessionLocal()
    try:
        row = (
            db.query(ActionOutcomeLog)
            .filter(ActionOutcomeLog.user_id == uid)
            .order_by(ActionOutcomeLog.id.desc())
            .first()
        )
        if not row:
            return None
        row_dict = {
            "id": row.id,
            "outcome_key": row.outcome_key,
            "action": row.action,
            "amount": row.amount,
            "success": bool(row.success),
            "tool_status": row.tool_status,
            "auto_resolved": bool(row.auto_resolved),
            "approved_by_human": bool(row.approved_by_human),
            "refund_reversed": bool(row.refund_reversed),
            "dispute_filed": bool(row.dispute_filed),
            "ticket_reopened": bool(getattr(row, "ticket_reopened", 0)),
            "crm_closed": bool(getattr(row, "crm_closed", 0)),
            "created_at": row.created_at,
        }
        summary = build_outcome_summary_for_ui(row_dict)
        # Keep UI surface compact + safe: do not leak tool_response_json.
        summary.pop("components", None)
        return summary
    except Exception:
        return None
    finally:
        db.close()


def build_outcome_insights(summary: dict[str, Any] | None, latest: dict[str, Any] | None) -> list[str]:
    """
    Deterministic, operator-safe micro-insights (1–3 lines).
    Never raises; never dramatic; never implies certainty beyond signals.
    """
    s = summary if isinstance(summary, dict) else {}
    latest_tier = (latest or {}).get("tier")
    tier = str(latest_tier or "unknown").lower()

    excellent = _safe_int(s.get("excellent", 0))
    good = _safe_int(s.get("good", 0))
    neutral = _safe_int(s.get("neutral", 0))
    bad = _safe_int(s.get("bad", 0))
    reopened = _safe_int(s.get("ticket_reopened", 0))
    reversed_n = _safe_int(s.get("refund_reversed", 0))
    disputes = _safe_int(s.get("dispute_filed", 0))
    assisted = _safe_int(s.get("assisted_success", 0))
    auto = _safe_int(s.get("auto_success", 0))

    total = excellent + good + neutral + bad
    lines: list[str] = []

    if total <= 0:
        return []

    if tier in {"excellent", "good", "neutral", "bad"}:
        label = "excellent" if tier == "excellent" else "good" if tier == "good" else "neutral" if tier == "neutral" else "poor"
        lines.append(f"Most recent outcome was {label}.")

    risk_events = reversed_n + disputes
    if risk_events > 0:
        lines.append("Refund reversals or disputes detected — review policy fit on recent motions.")
    elif reopened > max(1, total // 6):
        lines.append("Reopened tickets are elevated — consider tightening resolution steps.")
    else:
        # Stable if bad outcomes are not dominating and no major risk events.
        bad_rate = bad / max(1, total)
        if bad_rate <= 0.12:
            lines.append("Recent outcomes look stable.")

    if assisted > 0 and auto > 0:
        lines.append("Most successful outcomes are approval-reviewed.")
    elif assisted > 0 and auto == 0:
        lines.append("Most successful outcomes required operator review.")
    elif auto > 0 and assisted == 0:
        lines.append("Most successful outcomes were fully automatic.")

    # Keep to 1–3 short lines.
    out: list[str] = []
    for line in lines:
        t = str(line or "").strip()
        if t and t not in out:
            out.append(t)
        if len(out) >= 3:
            break
    return out


def _best_pattern_snapshot() -> dict[str, Any] | None:
    """
    Optional: select best performing pattern from the learning store.
    Returns None if unavailable or empty.
    """
    try:
        from state_store import load_state
        from learning import PATTERN_STORE_KEY

        patterns = load_state(PATTERN_STORE_KEY, {})
        if not isinstance(patterns, dict) or not patterns:
            return None

        best_key = None
        best_score = -1.0
        best_entry: dict[str, Any] | None = None

        for k, entry in patterns.items():
            if not isinstance(entry, dict):
                continue
            sc = _safe_float(entry.get("ema_score", 0.5), 0.5)
            n = _safe_int(entry.get("sample_count", 0), 0)
            if n < 3:
                continue
            if sc > best_score:
                best_score = sc
                best_key = str(k)
                best_entry = entry

        if not best_key or not best_entry:
            return None

        expectation = "high" if best_score >= 0.75 else "medium" if best_score >= 0.45 else "low"
        return {
            "pattern_key": best_key[:180],
            "expectation": expectation,
            "ema_score": round(float(best_score), 4),
            "sample_count": _safe_int(best_entry.get("sample_count", 0)),
        }
    except Exception:
        return None


def get_decision_outcome_stats(
    issue_type: str,
    action: str,
    *,
    limit: int = 300,
) -> dict[str, Any]:
    """
    Aggregate real outcomes for the same issue_type + action (recent window, deterministic order).

    Used for decision scoring and UI trust metadata. Safe when empty or on DB errors:
    returns neutral band, zero count, and null rates until enough samples exist.
    """
    _MIN_RATE_N = 5
    _MIN_BAND_N = 5

    lim = max(1, min(500, int(limit)))
    it = str(issue_type or "general_support").strip()[:64] or "general_support"
    act = str(action or "none").strip().lower()[:32] or "none"

    neutral: dict[str, Any] = {
        "similar_case_count": 0,
        "historical_success_rate": None,
        "historical_reopen_rate": None,
        "outcome_confidence_band": "medium",
        "failure_rate": None,
        "reverse_rate": None,
        "dispute_rate": None,
    }

    db = SessionLocal()
    try:
        rows = (
            db.query(ActionOutcomeLog)
            .filter(
                ActionOutcomeLog.issue_type == it,
                ActionOutcomeLog.action == act,
            )
            .order_by(ActionOutcomeLog.id.desc())
            .limit(lim)
            .all()
        )
        n = len(rows)
        if n == 0:
            return dict(neutral)

        successes = sum(1 for r in rows if int(r.success or 0))
        reopened = sum(1 for r in rows if int(getattr(r, "ticket_reopened", 0) or 0))
        reversed_n = sum(1 for r in rows if int(r.refund_reversed or 0))
        disputes = sum(1 for r in rows if int(r.dispute_filed or 0))

        sr = round(successes / n, 4)
        rr = round(reopened / n, 4)
        rev_r = round(reversed_n / n, 4)
        disp_r = round(disputes / n, 4)
        fail_r = round(1.0 - sr, 4)

        band = "medium"
        if n < _MIN_BAND_N:
            band = "medium"
        else:
            if (
                rr > 0.20
                or rev_r > 0.08
                or disp_r > 0.06
                or fail_r > 0.35
            ):
                band = "low"
            elif sr >= 0.88 and rr <= 0.06 and reversed_n == 0 and disputes == 0:
                band = "high"
            else:
                band = "medium"

        hist_sr = sr if n >= _MIN_RATE_N else None
        hist_rr = rr if n >= _MIN_RATE_N else None
        fail_rep = fail_r if n >= _MIN_RATE_N else None
        rev_rep = rev_r if n >= _MIN_RATE_N else None
        disp_rep = disp_r if n >= _MIN_RATE_N else None

        return {
            "similar_case_count": n,
            "historical_success_rate": hist_sr,
            "historical_reopen_rate": hist_rr,
            "outcome_confidence_band": band,
            "failure_rate": fail_rep,
            "reverse_rate": rev_rep,
            "dispute_rate": disp_rep,
        }
    except Exception:
        return dict(neutral)
    finally:
        db.close()


def outcome_intelligence_snapshot(limit: int = 25, user_id: str | None = None) -> dict[str, Any]:
    """
    UI-facing outcome intelligence snapshot.
    Cached briefly per workspace principal; never raises; returns {} when no outcome data exists.
    """
    import time as _time

    uid = str(user_id or "").strip()[:120]
    if not uid:
        return {}

    global _outcome_intel_cache, _outcome_intel_cache_ts
    now = _time.time()
    cache_key = uid
    cached = _outcome_intel_cache.get(cache_key)
    cached_ts = _outcome_intel_cache_ts.get(cache_key, 0.0)
    if cached and (now - cached_ts) < _OUTCOME_INTEL_TTL:
        return dict(cached)

    latest = latest_outcome_summary(user_id=uid)
    summary = summarize_recent_outcomes(limit=limit, user_id=uid)
    # If there are no outcomes at all, return empty to keep payload minimal.
    total = _safe_int(summary.get("excellent", 0)) + _safe_int(summary.get("good", 0)) + _safe_int(summary.get("neutral", 0)) + _safe_int(summary.get("bad", 0))
    if total <= 0 and not latest:
        _outcome_intel_cache.pop(cache_key, None)
        _outcome_intel_cache_ts.pop(cache_key, None)
        return {}

    insights = build_outcome_insights(summary, latest)
    # Cross-tenant learning store — omit from per-workspace dashboard surfaces.
    best_pattern = None

    snapshot: dict[str, Any] = {
        "latest": latest,
        "summary": summary,
        "insights": insights,
        "best_pattern": best_pattern,
    }

    _outcome_intel_cache[cache_key] = dict(snapshot)
    _outcome_intel_cache_ts[cache_key] = now
    return dict(snapshot)
