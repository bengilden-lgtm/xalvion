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

_DEFAULT_METRICS: dict[str, Any] = {
    "avg_confidence": 0.0,
    "avg_quality": 0.0,
    "total_interactions": 0,
    "total_refunds": 0,
    "total_credits": 0,
    "money_moved": 0.0,
}

_metrics_failure_logged = False
_metrics_pool_timeout_logged = False


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
        money_moved = (
            db.query(func.sum(AnalyticsEvent.amount))
            .filter(AnalyticsEvent.action.in_(["refund", "credit"]))
            .scalar()
            or 0.0
        )

        return {
            "avg_confidence": round(float(avg_conf), 2),
            "avg_quality": round(float(avg_qual), 2),
            "total_interactions": total,
            "total_refunds": total_refunds,
            "total_credits": total_credits,
            "money_moved": round(float(money_moved), 2),
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
