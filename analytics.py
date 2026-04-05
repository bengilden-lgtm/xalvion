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

from sqlalchemy import Column, Float, Integer, String, Text, func
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
    "revenue_saved": 0.0,
    "refund_cost": 0.0,
    "good_excellent_outcome_rate": 0.0,
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

    id              = Column(Integer, primary_key=True, autoincrement=True)
    time            = Column(String(32), nullable=False, index=True)
    user_input      = Column(Text, default="")
    confidence      = Column(Float, default=0.0)
    quality         = Column(Float, default=0.0)
    response_length = Column(Integer, default=0)
    issue_type      = Column(String(64), default="general_support")
    action          = Column(String(32), default="none")
    amount          = Column(Float, default=0.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_event(
    user_input:  str,
    response:    str,
    confidence:  float,
    quality:     float,
    issue_type:  str = "general_support",
    action:      str = "none",
    amount:      float = 0.0,
) -> None:
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
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_metrics() -> dict[str, Any]:
    global _metrics_failure_logged
    db = SessionLocal()
    try:
        total = db.query(AnalyticsEvent).count()
        if not total:
            out = dict(_DEFAULT_METRICS)
            out["total_interactions"] = 0
            return out

        avg_conf = db.query(func.avg(AnalyticsEvent.confidence)).scalar() or 0.0
        avg_qual = db.query(func.avg(AnalyticsEvent.quality)).scalar() or 0.0
        total_refunds = db.query(AnalyticsEvent).filter(AnalyticsEvent.action == "refund").count()
        total_credits = db.query(AnalyticsEvent).filter(AnalyticsEvent.action == "credit").count()
        review_n = db.query(AnalyticsEvent).filter(AnalyticsEvent.action == "review").count()
        money_moved = (
            db.query(func.sum(AnalyticsEvent.amount))
            .filter(AnalyticsEvent.action.in_(["refund", "credit"]))
            .scalar()
            or 0.0
        )
        refund_cost = (
            db.query(func.sum(AnalyticsEvent.amount))
            .filter(AnalyticsEvent.action == "refund")
            .scalar()
            or 0.0
        )
        credit_volume = (
            db.query(func.sum(AnalyticsEvent.amount))
            .filter(AnalyticsEvent.action == "credit")
            .scalar()
            or 0.0
        )
        auto_safe_n = db.query(AnalyticsEvent).filter(
            AnalyticsEvent.action.in_(["none", "credit"]),
            AnalyticsEvent.quality >= 0.85,
            AnalyticsEvent.confidence >= 0.82,
        ).count()
        review_rate = round(review_n / max(1, total) * 100, 2)
        auto_safe_rate = round(auto_safe_n / max(1, total) * 100, 2)
        revenue_saved = round(float(credit_volume) * 2.05 + max(0, total - review_n) * 0.35, 2)

        approval_rate = 0.0
        good_excellent_outcome_rate = 0.0
        try:
            from outcome_store import get_outcome_stats as _outcome_stats

            ost = _outcome_stats()
            ot = max(1, int(ost.get("total", 0) or 0))
            approval_rate = round(float(ost.get("human_approved", 0) or 0) / ot * 100, 2)
            good_excellent_outcome_rate = float(ost.get("good_excellent_outcome_rate", 0.0) or 0.0)
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
            "revenue_saved": revenue_saved,
            "refund_cost": round(float(refund_cost), 2),
            "good_excellent_outcome_rate": round(good_excellent_outcome_rate, 2),
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
