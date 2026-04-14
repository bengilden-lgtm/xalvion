from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, String, Text

from db import Base


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    usage = Column(Integer, default=0, nullable=False)
    tier = Column(String, default="free", nullable=False)
    role = Column(String, default="operator", nullable=False)
    stripe_connected = Column(Integer, default=0, nullable=False)
    stripe_account_id = Column(String, nullable=True)
    stripe_livemode = Column(Integer, default=0, nullable=False)
    stripe_scope = Column(String, nullable=True)
    stripe_subscription_id = Column(String(128), nullable=True)
    stripe_subscription_status = Column(String(32), nullable=True)
    stripe_tier_source = Column(String(16), nullable=True)  # "webhook" | "manual" | "bypass"


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    ticket_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    amount = Column(Float, default=0.0)
    issue_type = Column(String, default="general_support")
    reason = Column(String, default="")
    status = Column(String, default="executed")
    confidence = Column(Float, default=0.0)
    quality = Column(Float, default=0.0)
    message_snippet = Column(Text, default="")
    requires_approval = Column(Integer, default=0)
    approved = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_actionlog_ticket", "ticket_id"),
        Index("ix_actionlog_user_ts", "username", "timestamp"),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    username = Column(String, nullable=False, index=True)
    customer_email = Column(String(320), nullable=True)
    channel = Column(String, default="web")
    source = Column(String, default="workspace")
    status = Column(String, default="new", index=True)
    queue = Column(String, default="new", index=True)
    priority = Column(String, default="medium", index=True)
    risk_level = Column(String, default="medium", index=True)
    issue_type = Column(String, default="general_support", index=True)
    subject = Column(Text, default="")
    customer_message = Column(Text, default="")
    final_reply = Column(Text, default="")
    internal_note = Column(Text, default="")
    action = Column(String, default="none")
    amount = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    quality = Column(Float, default=0.0)
    requires_approval = Column(Integer, default=0)
    approved = Column(Integer, default=0)
    churn_risk = Column(Integer, default=0)
    refund_likelihood = Column(Integer, default=0)
    abuse_likelihood = Column(Integer, default=0)
    complexity = Column(Integer, default=0)
    urgency = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_ticket_user_status", "username", "status"),
        Index("ix_ticket_queue_priority", "queue", "priority"),
        Index("ix_ticket_churn", "churn_risk"),
        Index("ix_ticket_issue_type", "issue_type"),
    )

