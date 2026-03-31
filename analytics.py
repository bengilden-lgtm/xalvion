"""
analytics.py — event logging and metrics.

FIX: Original wrote to a flat analytics.json while everything else uses
     SQLite (aurum.db).  This version uses the same SQLAlchemy engine so
     all data lives in one place, survives concurrent writes safely, and
     works on read-only filesystems where JSON writes would silently fail.

     Backwards-compatible: get_metrics() returns the same dict shape.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aurum.db")
_engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
_Base = declarative_base()
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


class _AnalyticsEvent(_Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(String, nullable=False, index=True)
    user_input = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    quality = Column(Float, default=0.0)
    response_length = Column(Integer, default=0)


_Base.metadata.create_all(bind=_engine)


def log_event(
    user_input: str,
    response: str,
    confidence: float,
    quality: float,
) -> None:
    db = _Session()
    try:
        event = _AnalyticsEvent(
            time=str(datetime.utcnow()),
            user_input=(user_input or "")[:500],
            confidence=round(float(confidence or 0), 4),
            quality=round(float(quality or 0), 4),
            response_length=len(response or ""),
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_metrics() -> dict[str, Any]:
    db = _Session()
    try:
        total = db.query(_AnalyticsEvent).count()
        if not total:
            return {}

        avg_conf = db.query(func.avg(_AnalyticsEvent.confidence)).scalar() or 0.0
        avg_qual = db.query(func.avg(_AnalyticsEvent.quality)).scalar() or 0.0

        return {
            "avg_confidence": round(float(avg_conf), 2),
            "avg_quality": round(float(avg_qual), 2),
            "total_interactions": total,
        }
    finally:
        db.close()
