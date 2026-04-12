"""
analytics.py — Event logging and metrics.

FIX: Was creating its own SQLAlchemy engine pointing at the same aurum.db
file as state_store.py and persistence_layer.py.  Now uses the shared engine
from db.py so there is exactly one connection pool for the entire process.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, func, inspect, text
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError

from db import Base, SessionLocal, engine

logger = logging.getLogger("xalvion.analytics")
_xalvion_logger = logging.getLogger("xalvion")

_DEFAULT_METRICS: dict[str, Any] = {
    "avg_confidence": 0.0,
    "avg_quality": 0.0,
    "total_interactions": 0,
    "total_refunds": 0,
    "total_credits": 0,
    "money_moved": 0.0,
    "approval_rate": 0.0,
    "auto_safe_rate": 0.0,
    "review_rate": 0.0,
    "refund_cost": 0.0,
    "credit_volume_usd": 0.0,
    "good_excellent_outcome_rate": 0.0,
    "has_analytics_data": False,
}

_metrics_failure_logged = False
_metrics_pool_timeout_logged = False
_outcome_stats_enrich_fail_logged = False


def _log_metrics_pool_timeout_once(exc: BaseException) -> None:
    global _metrics_pool_timeout_logged
    if _metrics_pool_timeout_logged:
        return
    _metrics_pool_timeout_logged = True
    logger.warning(
        "get_metrics_timeout_fallback type=%s detail=%s",
        type(exc).__name__,
        str(exc)[:400],
    )


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    time             = Column(String(32), nullable=False, index=True)
    user_input       = Column(Text, default="")
    confidence       = Column(Float, default=0.0)
    quality          = Column(Float, default=0.0)
    response_length  = Column(Integer, default=0)
    issue_type       = Column(String(64), default="general_support")
    action           = Column(String(32), default="none")
    amount           = Column(Float, default=0.0)
    actor_principal  = Column(String(120), nullable=False, default="")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_analytics_actor_column_ready = False


def ensure_analytics_actor_principal_column() -> None:
    """SQLite lazy migration: tenant key for analytics (account or guest client id)."""
    global _analytics_actor_column_ready
    if _analytics_actor_column_ready:
        return
    try:
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("analytics_events")}
        if "actor_principal" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE analytics_events ADD COLUMN actor_principal VARCHAR(120) DEFAULT ''")
                )
    except Exception:
        logger.warning("analytics_actor_principal_migration_failed", exc_info=True)
    _analytics_actor_column_ready = True


def log_event(
    user_input:  str,
    response:    str,
    confidence:  float,
    quality:     float,
    issue_type:  str = "general_support",
    action:      str = "none",
    amount:      float = 0.0,
    *,
    actor_principal: str | None = None,
) -> None:
    ensure_analytics_actor_principal_column()
    db = SessionLocal()
    try:
        event = AnalyticsEvent(
            time=datetime.now(timezone.utc).isoformat(),
            user_input=(user_input or "")[:500],
            confidence=round(float(confidence or 0), 4),
            quality=round(float(quality or 0), 4),
            response_length=len(response or ""),
            issue_type=(issue_type or "general_support")[:64],
            action=(action or "none")[:32],
            amount=round(float(amount or 0), 2),
            actor_principal=str(actor_principal or "")[:120],
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_metrics(actor_principal: str | None = None) -> dict[str, Any]:
    """Aggregate analytics_events for one workspace principal (matches ``actor_principal`` on log_event).

    Without a principal we return empty-shaped metrics so callers never read cross-tenant aggregates.
    """
    global _metrics_failure_logged
    principal = str(actor_principal or "").strip()[:120]
    if not principal:
        return dict(_DEFAULT_METRICS)

    db = SessionLocal()
    try:
        scope = db.query(AnalyticsEvent).filter(AnalyticsEvent.actor_principal == principal)
        total = int(scope.count() or 0)
        if not total:
            out = dict(_DEFAULT_METRICS)
            out["total_interactions"] = 0
            out["has_analytics_data"] = False
            return out

        try:
            avg_conf = (
                db.query(func.avg(AnalyticsEvent.confidence))
                .filter(AnalyticsEvent.actor_principal == principal)
                .scalar()
                or 0.0
            )
        except OperationalError:
            avg_conf = 0.0
        try:
            avg_qual = (
                db.query(func.avg(AnalyticsEvent.quality))
                .filter(AnalyticsEvent.actor_principal == principal)
                .scalar()
                or 0.0
            )
        except OperationalError:
            avg_qual = 0.0

        # Older schemas may not have action/amount columns. Preserve total_interactions regardless.
        try:
            total_refunds = int(scope.filter(AnalyticsEvent.action == "refund").count() or 0)
            total_credits = int(scope.filter(AnalyticsEvent.action == "credit").count() or 0)
            review_n = int(scope.filter(AnalyticsEvent.action == "review").count() or 0)
        except OperationalError:
            total_refunds = 0
            total_credits = 0
            review_n = 0

        try:
            money_moved = (
                db.query(func.sum(AnalyticsEvent.amount))
                .filter(
                    AnalyticsEvent.actor_principal == principal,
                    AnalyticsEvent.action.in_(["refund", "credit"]),
                )
                .scalar()
                or 0.0
            )
            refund_cost = (
                db.query(func.sum(AnalyticsEvent.amount))
                .filter(AnalyticsEvent.actor_principal == principal, AnalyticsEvent.action == "refund")
                .scalar()
                or 0.0
            )
            credit_volume = (
                db.query(func.sum(AnalyticsEvent.amount))
                .filter(AnalyticsEvent.actor_principal == principal, AnalyticsEvent.action == "credit")
                .scalar()
                or 0.0
            )
        except OperationalError:
            money_moved = 0.0
            refund_cost = 0.0
            credit_volume = 0.0

        try:
            auto_safe_n = int(
                scope.filter(
                    AnalyticsEvent.action.in_(["none", "credit"]),
                    AnalyticsEvent.quality >= 0.85,
                    AnalyticsEvent.confidence >= 0.82,
                ).count()
                or 0
            )
        except OperationalError:
            auto_safe_n = 0
        review_rate = round(review_n / max(1, total) * 100, 2)
        auto_safe_rate = round(auto_safe_n / max(1, total) * 100, 2)

        approval_rate = 0.0
        good_excellent_outcome_rate = 0.0
        outcome_quality_mix: dict[str, int] | None = None
        recent_risk_events: int | None = None
        reviewed_motion_rate: float | None = None
        try:
            from outcome_store import get_outcome_stats as _outcome_stats

            ost = _outcome_stats(principal)
            ot = max(1, int(ost.get("total", 0) or 0))
            approval_rate = round(float(ost.get("human_approved", 0) or 0) / ot * 100, 2)
            good_excellent_outcome_rate = float(ost.get("good_excellent_outcome_rate", 0.0) or 0.0)

            # Optional enrichments for workspace intelligence surfaces.
            try:
                from outcome_store import summarize_recent_outcomes as _summ_recent

                mix = _summ_recent(limit=50, user_id=principal)
                if isinstance(mix, dict):
                    outcome_quality_mix = {
                        "excellent": int(mix.get("excellent", 0) or 0),
                        "good": int(mix.get("good", 0) or 0),
                        "neutral": int(mix.get("neutral", 0) or 0),
                        "bad": int(mix.get("bad", 0) or 0),
                    }
                    recent_risk_events = int(mix.get("refund_reversed", 0) or 0) + int(mix.get("dispute_filed", 0) or 0) + int(mix.get("ticket_reopened", 0) or 0)
            except Exception:
                outcome_quality_mix = None
                recent_risk_events = None

            try:
                outcome_total = float(ost.get("total", 0) or 0)
                human = float(ost.get("human_approved", 0) or 0)
                reviewed_motion_rate = round((human / max(1.0, outcome_total)) * 100, 2)
            except Exception:
                reviewed_motion_rate = None
        except Exception:
            global _outcome_stats_enrich_fail_logged
            if not _outcome_stats_enrich_fail_logged:
                _outcome_stats_enrich_fail_logged = True
                _xalvion_logger.warning(
                    "get_metrics: outcome_store.get_outcome_stats enrichment unavailable",
                    exc_info=True,
                )

        return {
            "avg_confidence": round(float(avg_conf), 2),
            "avg_quality": round(float(avg_qual), 2),
            "total_interactions": total,
            "total_refunds": total_refunds,
            "total_credits": total_credits,
            "money_moved": round(float(money_moved), 2),
            "approval_rate": approval_rate,
            "auto_safe_rate": auto_safe_rate,
            "review_rate": review_rate,
            "refund_cost": round(float(refund_cost), 2),
            "credit_volume_usd": round(float(credit_volume), 2),
            "good_excellent_outcome_rate": round(good_excellent_outcome_rate, 2),
            "has_analytics_data": True,
            # Optional additions: safe for old clients (ignored if unknown).
            "outcome_quality_mix": outcome_quality_mix,
            "recent_risk_events": recent_risk_events,
            "reviewed_motion_rate": reviewed_motion_rate,
        }
    except SQLTimeoutError as exc:
        _log_metrics_pool_timeout_once(exc)
        return dict(_DEFAULT_METRICS)
    except OperationalError as exc:
        if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
            _log_metrics_pool_timeout_once(exc)
            return dict(_DEFAULT_METRICS)
        if not _metrics_failure_logged:
            _metrics_failure_logged = True
            logger.warning(
                "get_metrics_unavailable type=%s detail=%s",
                type(exc).__name__,
                str(exc)[:500],
            )
        return dict(_DEFAULT_METRICS)
    except Exception as exc:
        if not _metrics_failure_logged:
            _metrics_failure_logged = True
            logger.warning(
                "get_metrics_unavailable type=%s detail=%s",
                type(exc).__name__,
                str(exc)[:500],
            )
        return dict(_DEFAULT_METRICS)
    finally:
        db.close()
