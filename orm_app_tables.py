"""
ORM tables that historically lived in app.py.

Kept in a dedicated module so Railway pre-deploy and db.init_db() can register
all models on the shared Base without importing the full FastAPI application.
"""

from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, Text

from db import Base


class OperatorState(Base):
    __tablename__ = "operator_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(String, default="balanced", nullable=False)
    updated_at = Column(String, nullable=False)
    updated_by = Column(String, default="system")


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    processed_at = Column(String, nullable=False)
    outcome = Column(String, default="ok")
    detail = Column(Text, default="")


class PendingCheckout(Base):
    __tablename__ = "pending_checkouts"

    # VERIFICATION FIX: B6 — provide minimum required columns for pending checkout integrity
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(256), nullable=True, index=True)
    stripe_session_id = Column(String(128), nullable=True, index=True, unique=True)
    plan_tier = Column(String(32), nullable=True)

    session_id = Column(String(128), primary_key=True)
    username = Column(String(256), nullable=False, index=True)
    tier = Column(String(32), nullable=False)
    created_at = Column(String(32), nullable=False)
    completed_at = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    # status: "pending" | "completed" | "expired" | "failed"


class GuestPreviewUsage(Base):
    """Server-side tally for unauthenticated workspace preview runs (abuse hardening)."""

    __tablename__ = "guest_preview_usage"

    client_id = Column(String(80), primary_key=True)
    usage_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(String, nullable=False)


class RateLimitEvent(Base):
    """
    DB-backed sliding-window rate limit log.
    Behavior must match the prior in-memory limiter: max 12 events per 60 seconds per key.
    """

    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(96), nullable=False, index=True)
    ts = Column(Float, nullable=False, index=True)  # epoch seconds


class OperatorMonthlyUsage(Base):
    """Successful operator runs per calendar month, split by workspace for attribution."""

    __tablename__ = "operator_monthly_usage"

    account_username = Column(String(96), primary_key=True)
    workspace_id = Column(String(80), primary_key=True)
    period_key = Column(String(7), primary_key=True)  # UTC YYYY-MM
    run_count = Column(Integer, nullable=False, default=0)
