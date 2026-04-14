from __future__ import annotations

"""
schemas.py — Pydantic request and response models for the Xalvion API.

Owns:
  - All HTTP request body models (AuthRequest, SupportRequest, etc.)
  - All HTTP response shape contracts defined as Pydantic models

Does NOT own:
  - ORM models (orm_models.py, orm_app_tables.py)
  - Business logic
  - Plan configuration

Imports from:
  - pydantic (external)
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


VALID_OP_MODES = {"conservative", "balanced", "delight", "fraud_aware"}


class AuthRequest(BaseModel):
    username: str
    password: str


class SupportRequest(BaseModel):
    message: str
    sentiment: int | None = None
    ltv: int | None = None
    order_status: str | None = None
    payment_intent_id: str | None = None
    charge_id: str | None = None
    refund_reason: str | None = None
    channel: str | None = None
    source: str | None = None
    customer_email: str | None = None
    request_context: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("message required")
        if len(text) > 10000:
            raise ValueError("message too long")
        return text

    @field_validator("customer_email")
    @classmethod
    def validate_customer_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if "@" not in s:
            raise ValueError("customer_email must look like an email address")
        if len(s) > 320:
            raise ValueError("customer_email too long")
        return s

    @field_validator("request_context")
    @classmethod
    def validate_request_context(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("request_context must be an object")
        return v


class TicketReplySendRequest(BaseModel):
    """Optional overrides when emailing ``ticket.final_reply`` to the customer."""

    body: str | None = None
    subject: str | None = None

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return s[:998]


class UpgradeRequest(BaseModel):
    tier: str
    upgrade_trigger: str | None = None


class AdminUserAction(BaseModel):
    username: str


class OperatorModeRequest(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        normalized = (v or "").strip().lower()
        if normalized not in VALID_OP_MODES:
            raise ValueError(f"mode must be one of {sorted(VALID_OP_MODES)}")
        return normalized


class TicketStatusRequest(BaseModel):
    status: str | None = None
    queue: str | None = None
    priority: str | None = None
    internal_note: str | None = None


class RefundActionRequest(BaseModel):
    payment_intent_id: str | None = None
    charge_id: str | None = None
    amount: float | None = None
    refund_reason: str | None = None


class ApprovalDecisionRequest(BaseModel):
    payment_intent_id: str | None = None
    charge_id: str | None = None
    refund_reason: str | None = None
    internal_note: str | None = None
    # Customer-facing reply refined in workspace before approve (optional, capped).
    final_reply: str | None = None


class ChargeActionRequest(BaseModel):
    customer_id: str
    payment_method_id: str
    amount: int
    currency: str = "usd"
    description: str | None = None

