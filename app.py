"""
Xalvion Sovereign Brain — app.py
Production-grade FastAPI backend for an AI support/ticketing SaaS.

Sections:
  1.  Imports & Config
  2.  Database Engine
  3.  Models
  4.  Enum Constants & Validators
  5.  Pydantic Schemas
  6.  Auth Helpers
  7.  Plan & Usage Helpers
  8.  Operator & Ticket Helpers
  9.  Serialization Helpers
  10. Billing Helpers (Stripe)
  11. Support Pipeline
  12. Streaming Helpers
  13. Routes — Static
  14. Routes — Health
  15. Routes — Auth
  16. Routes — Billing & Plans
  17. Routes — Dashboard & Metrics
  18. Routes — Tickets
  19. Routes — Admin
  20. Routes — Support
  21. Entrypoint
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, AsyncIterator

import stripe
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy import (
    Column, Float, Index, Integer, String, Text,
    create_engine, func,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from agent import run_agent

try:
    from analytics import get_metrics
except Exception:
    def get_metrics() -> dict[str, Any]:
        return {}


load_dotenv(override=True)

# =============================================================================
# 1. CONFIG
# =============================================================================

SECRET_KEY           = os.getenv("JWT_SECRET", "dev_secret_change_me")
ALGORITHM            = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "120"))
ADMIN_USERNAME       = os.getenv("ADMIN_USERNAME", "").strip()

STRIPE_KEY             = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO       = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_ELITE     = os.getenv("STRIPE_PRICE_ELITE", "").strip()
ALLOW_DIRECT_BILLING_BYPASS = (
    os.getenv("ALLOW_DIRECT_BILLING_BYPASS", "false").strip().lower() == "true"
)

FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://127.0.0.1:8001").rstrip("/")
CHECKOUT_SUCCESS_URL = os.getenv("CHECKOUT_SUCCESS_URL", f"{FRONTEND_URL}?checkout=success")
CHECKOUT_CANCEL_URL  = os.getenv("CHECKOUT_CANCEL_URL",  f"{FRONTEND_URL}?checkout=cancel")

STREAM_CHUNK_SIZE  = 18
STREAM_CHUNK_DELAY = 0.02
STATUS_STEP_DELAY  = 0.22
MAX_AUTO_REFUND    = 50

APPROVAL_THRESHOLD = float(os.getenv("APPROVAL_THRESHOLD", "25.00"))
LIVE_MODE          = os.getenv("LIVE_MODE", "false").strip().lower() == "true"

REFUND_RULES: dict[str, Any] = {
    "enabled": True,
    "allowed_tiers": {"pro", "elite"},
    "max_auto_refund_amount": 50.00,
    "allowed_issue_types": {
        "duplicate_charge", "double_charge", "billing_issue",
        "payment_issue", "refund_request", "billing_duplicate_charge",
        "general_support",
    },
    "blocked_order_statuses": set(),
    "min_confidence": 0.5,
    "min_quality":    0.5,
}

PLAN_CONFIG: dict[str, dict[str, Any]] = {
    "free":  {"monthly_limit": 50,    "history_limit": 20,    "streaming": True, "dashboard_access": "basic",    "priority_routing": False, "team_seats": 1,   "label": "Free"},
    "pro":   {"monthly_limit": 500,   "history_limit": 500,   "streaming": True, "dashboard_access": "full",     "priority_routing": True,  "team_seats": 3,   "label": "Pro"},
    "elite": {"monthly_limit": 5000,  "history_limit": 5000,  "streaming": True, "dashboard_access": "advanced", "priority_routing": True,  "team_seats": 20,  "label": "Elite"},
    "dev":   {"monthly_limit": 10**9, "history_limit": 10**9, "streaming": True, "dashboard_access": "advanced", "priority_routing": True,  "team_seats": 999, "label": "Dev"},
}

PUBLIC_PLAN_TIERS = {"free", "pro", "elite"}
PRICE_MAP = {"pro": STRIPE_PRICE_PRO, "elite": STRIPE_PRICE_ELITE}

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

BASE_DIR     = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
INDEX_PATH   = os.path.join(BASE_DIR, "index.html")
APP_JS_PATH  = os.path.join(BASE_DIR, "app.js")
LANDING_PATH = os.path.join(BASE_DIR, "landing.html")
FLUID_DIR    = os.path.join(BASE_DIR, "fluid")

# =============================================================================
# FastAPI App + CORS
# =============================================================================

app = FastAPI(title="Xalvion Sovereign Brain")

if os.path.isdir(FLUID_DIR):
    app.mount("/fluid", StaticFiles(directory=FLUID_DIR), name="fluid")

_ALLOWED_ORIGINS = [
    "http://localhost:5500", "http://127.0.0.1:5500",
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:8001", "http://127.0.0.1:8001",
    "https://www.xalvion.tech", "https://xalvion.tech",
]
for _o in [FRONTEND_URL] + [
    x.strip().rstrip("/")
    for x in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if x.strip()
]:
    if _o and _o not in _ALLOWED_ORIGINS:
        _ALLOWED_ORIGINS.append(_o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# 2. DATABASE ENGINE
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aurum.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,   # reconnect after idle/stale connections (Railway)
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_rate_log: dict[str, list[float]] = {}  # in-process per-user rate limiter


def _now_iso() -> str:
    """Canonical UTC ISO timestamp for all string timestamp columns."""
    return datetime.utcnow().isoformat()


# =============================================================================
# 3. MODELS
# =============================================================================

class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    usage    = Column(Integer, default=0, nullable=False)
    tier     = Column(String,  default="free", nullable=False)


class ActionLog(Base):
    """
    Immutable audit record of every support action.
    ticket_id is an explicit FK reference to Ticket — enables precise
    approval sync without any fuzzy "most recent ticket" logic.
    """
    __tablename__ = "action_logs"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    timestamp         = Column(String,  nullable=False, index=True)
    username          = Column(String,  nullable=False, index=True)
    ticket_id         = Column(Integer, nullable=True,  index=True)
    action            = Column(String,  nullable=False)
    amount            = Column(Float,   default=0.0)
    issue_type        = Column(String,  default="general_support")
    reason            = Column(String,  default="")
    status            = Column(String,  default="executed")
    confidence        = Column(Float,   default=0.0)
    quality           = Column(Float,   default=0.0)
    message_snippet   = Column(Text,    default="")
    requires_approval = Column(Integer, default=0)
    approved          = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_actionlog_ticket",  "ticket_id"),
        Index("ix_actionlog_user_ts", "username", "timestamp"),
    )


class Ticket(Base):
    """
    Core operational record — one row per support request.
    Every field that flows through business logic is indexed or validated.
    """
    __tablename__ = "tickets"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    created_at        = Column(String,  nullable=False)
    updated_at        = Column(String,  nullable=False)
    username          = Column(String,  nullable=False, index=True)
    channel           = Column(String,  default="web")
    source            = Column(String,  default="workspace")
    status            = Column(String,  default="new",    index=True)
    queue             = Column(String,  default="new",    index=True)
    priority          = Column(String,  default="medium", index=True)
    risk_level        = Column(String,  default="medium", index=True)
    issue_type        = Column(String,  default="general_support", index=True)
    subject           = Column(Text,    default="")
    customer_message  = Column(Text,    default="")
    final_reply       = Column(Text,    default="")
    internal_note     = Column(Text,    default="")
    action            = Column(String,  default="none")
    amount            = Column(Float,   default=0.0)
    confidence        = Column(Float,   default=0.0)
    quality           = Column(Float,   default=0.0)
    requires_approval = Column(Integer, default=0)
    approved          = Column(Integer, default=0)
    churn_risk        = Column(Integer, default=0)
    refund_likelihood = Column(Integer, default=0)
    abuse_likelihood  = Column(Integer, default=0)
    complexity        = Column(Integer, default=0)
    urgency           = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_ticket_user_status",    "username", "status"),
        Index("ix_ticket_queue_priority", "queue",    "priority"),
        Index("ix_ticket_churn",          "churn_risk"),
        Index("ix_ticket_issue_type",     "issue_type"),
    )


class OperatorState(Base):
    """
    Singleton — first row is always used.
    Stores the global operator mode + who last changed it.
    """
    __tablename__ = "operator_state"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    mode       = Column(String,  default="balanced", nullable=False)
    updated_at = Column(String,  nullable=False)
    updated_by = Column(String,  default="system")


class ProcessedWebhook(Base):
    """
    Stripe webhook idempotency table.
    Event is claimed (inserted) BEFORE side effects.
    outcome tracks: processing → ok | failed | skipped
    detail stores failure reason when outcome=failed.
    """
    __tablename__ = "processed_webhooks"

    event_id     = Column(String, primary_key=True)
    event_type   = Column(String, nullable=False)
    processed_at = Column(String, nullable=False)
    outcome      = Column(String, default="ok")
    detail       = Column(Text,   default="")


# Creates all missing tables on startup — safe for SQLite and Railway Postgres.
Base.metadata.create_all(bind=engine)

# =============================================================================
# 4. ENUM CONSTANTS & VALIDATORS
# Single source of truth — every mutation path uses these.
# =============================================================================

VALID_QUEUES     = {"new", "waiting", "escalated", "refund_risk", "vip", "resolved"}
VALID_STATUSES   = {"new", "waiting", "escalated", "resolved", "failed"}
VALID_PRIORITIES = {"low", "medium", "high"}
VALID_RISKS      = {"low", "medium", "high"}
VALID_OP_MODES   = {"conservative", "balanced", "delight", "fraud_aware"}
VALID_CHANNELS   = {"web", "email", "api", "chat", "mobile"}
VALID_SOURCES    = {"workspace", "sdk", "api", "webhook", "import"}


def _safe_queue(value: Any, default: str = "new") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_QUEUES else default


def _safe_status(value: Any, default: str = "new") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_STATUSES else default


def _safe_priority(value: Any, default: str = "medium") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_PRIORITIES else default


def _safe_risk(value: Any, default: str = "medium") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_RISKS else default


def _safe_op_mode(value: Any, default: str = "balanced") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_OP_MODES else default


def _safe_channel(value: Any, default: str = "web") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_CHANNELS else default


def _safe_source(value: Any, default: str = "workspace") -> str:
    v = (str(value or "") or default).strip().lower()
    return v if v in VALID_SOURCES else default


def _clamp(value: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value or 0)))
    except (TypeError, ValueError):
        return lo

# =============================================================================
# 5. PYDANTIC SCHEMAS
# =============================================================================


class AuthRequest(BaseModel):
    username: str
    password: str


class SupportRequest(BaseModel):
    message:           str
    sentiment:         int | None = None
    ltv:               int | None = None
    order_status:      str | None = None
    payment_intent_id: str | None = None
    charge_id:         str | None = None
    refund_reason:     str | None = None
    channel:           str | None = None
    source:            str | None = None


class UpgradeRequest(BaseModel):
    tier: str


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
    """Admin-only ticket mutation. All fields optional — only provided fields are changed."""
    status:        str | None = None
    queue:         str | None = None
    priority:      str | None = None
    internal_note: str | None = None

# =============================================================================
# 6. AUTH HELPERS
# =============================================================================


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > 72:
        password = pw[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        return User(username="guest", password="", usage=0, tier="free")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token    = authorization.split(" ", 1)[1].strip()
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_authenticated_user(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "username", "") in {"", "guest"}:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not ADMIN_USERNAME or user.username != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def check_rate_limit(user_id: str) -> bool:
    """In-process sliding-window rate limiter. 12 req/min per user."""
    # Guest users share a single bucket — prevents unauthenticated spam
    key = user_id if user_id and user_id != "guest" else "__guest__"
    now = time.time()
    _rate_log.setdefault(key, [])
    _rate_log[key] = [t for t in _rate_log[key] if now - t < 60]
    if len(_rate_log[key]) >= 12:
        return False
    _rate_log[key].append(now)
    return True

# =============================================================================
# 7. PLAN & USAGE HELPERS
# =============================================================================


def get_plan_name(user: User | None) -> str:
    if not user:
        return "free"
    tier = (getattr(user, "tier", None) or "free").strip().lower()
    return tier if tier in PLAN_CONFIG else "free"


def get_public_plan_name(user: User | None) -> str:
    tier = get_plan_name(user)
    return tier if tier in PUBLIC_PLAN_TIERS else "free"


def get_plan_config(tier: str | None) -> dict[str, Any]:
    return PLAN_CONFIG.get((tier or "free").strip().lower(), PLAN_CONFIG["free"])


def get_usage_summary(user: User | None) -> dict[str, Any]:
    plan_name = get_plan_name(user)
    plan      = get_plan_config(plan_name)
    usage     = int(getattr(user, "usage", 0) or 0)
    limit     = int(plan["monthly_limit"])
    remaining = max(0, limit - usage) if limit < 10**9 else limit
    return {
        "tier":             plan_name,
        "label":            plan["label"],
        "usage":            usage,
        "limit":            limit,
        "remaining":        remaining,
        "dashboard_access": plan["dashboard_access"],
        "priority_routing": plan["priority_routing"],
    }


def build_upgrade_payload(current_tier: str) -> dict[str, Any]:
    current_key = current_tier if current_tier in PUBLIC_PLAN_TIERS else "free"
    suggestions = (
        ["pro", "elite"] if current_key == "free"
        else ["elite"]   if current_key == "pro"
        else []
    )
    return {
        "current_tier":       current_key,
        "available_upgrades": suggestions,
        "plans": {
            tier: {
                "label":            cfg["label"],
                "monthly_limit":    cfg["monthly_limit"],
                "history_limit":    cfg["history_limit"],
                "dashboard_access": cfg["dashboard_access"],
                "priority_routing": cfg["priority_routing"],
                "team_seats":       cfg["team_seats"],
                "checkout_ready":   bool(PRICE_MAP.get(tier)),
            }
            for tier, cfg in PLAN_CONFIG.items()
            if tier in PUBLIC_PLAN_TIERS
        },
    }


def enforce_plan_limits(user: User) -> None:
    plan_name = get_plan_name(user)
    plan      = get_plan_config(plan_name)

    if not check_rate_limit(user.username):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    usage = int(getattr(user, "usage", 0) or 0)
    limit = int(plan["monthly_limit"])
    if usage >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"{plan['label']} plan limit reached. "
                f"Used {usage}/{limit} tickets. Upgrade to continue."
            ),
            headers={"X-Xalvion-Plan": plan_name, "X-Xalvion-Limit": str(limit)},
        )

# =============================================================================
# 8. OPERATOR & TICKET HELPERS
# =============================================================================


def get_operator_mode(db: Session) -> str:
    state = db.query(OperatorState).order_by(OperatorState.id.asc()).first()
    if not state:
        state = OperatorState(mode="balanced", updated_at=_now_iso(), updated_by="system")
        db.add(state)
        db.commit()
        db.refresh(state)
    return _safe_op_mode(state.mode)


def set_operator_mode(db: Session, mode: str, by: str = "admin") -> str:
    normalized = _safe_op_mode(mode)
    if normalized not in VALID_OP_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operator mode. Must be one of: {sorted(VALID_OP_MODES)}",
        )
    state = db.query(OperatorState).order_by(OperatorState.id.asc()).first()
    if not state:
        state = OperatorState(mode=normalized, updated_at=_now_iso(), updated_by=by)
        db.add(state)
    else:
        state.mode       = normalized
        state.updated_at = _now_iso()
        state.updated_by = by
    db.commit()
    return normalized


def build_agent_meta(req: SupportRequest, user: User, db: Session | None = None) -> dict[str, Any]:
    plan_name     = get_plan_name(user)
    operator_mode = get_operator_mode(db) if db is not None else "balanced"
    return {
        "sentiment":         req.sentiment if req.sentiment is not None else 5,
        "ltv":               req.ltv if req.ltv is not None else 0,
        "order_status":      req.order_status if req.order_status is not None else "unknown",
        "plan_tier":         plan_name,
        "priority_routing":  get_plan_config(plan_name)["priority_routing"],
        "payment_intent_id": (req.payment_intent_id or "").strip(),
        "charge_id":         (req.charge_id or "").strip(),
        "operator_mode":     operator_mode,
        "channel":           _safe_channel(req.channel),
        "source":            _safe_source(req.source),
    }


def create_ticket_record(db: Session, user: User, req: SupportRequest) -> Ticket:
    now    = _now_iso()
    ticket = Ticket(
        created_at       = now,
        updated_at       = now,
        username         = str(getattr(user, "username", "unknown") or "unknown"),
        channel          = _safe_channel(req.channel),
        source           = _safe_source(req.source),
        subject          = (req.message or "")[:300],
        customer_message = (req.message or "")[:2000],
        status           = "new",
        queue            = "new",
        priority         = "medium",
        risk_level       = "medium",
        issue_type       = "general_support",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_from_result(db: Session, ticket: Ticket, result: dict[str, Any]) -> Ticket:
    """
    Persist agent result into Ticket.
    Every enum field is validated. Triage scores are clamped 0–99.
    Derives status from action + tool_status so logic is in one place.
    """
    decision  = result.get("decision") or {}
    triage    = result.get("triage")   or {}
    output    = result.get("output")   or {}
    action    = str(result.get("action", "none") or "none")
    raw_queue = str(decision.get("queue", "new") or "new")

    tool_status = str(result.get("tool_status", "") or "").lower()
    if tool_status in {"pending_approval", "manual_review"}:
        status = "waiting"
    elif action in {"refund", "credit", "none"}:
        status = "resolved"
    else:
        status = "escalated"
    if raw_queue == "resolved":
        status = "resolved"

    ticket.updated_at        = _now_iso()
    ticket.status            = _safe_status(status)
    ticket.queue             = _safe_queue(raw_queue)
    ticket.priority          = _safe_priority(
        decision.get("priority")
        or (result.get("meta") or {}).get("priority")
        or "medium"
    )
    ticket.risk_level        = _safe_risk(decision.get("risk_level") or "medium")
    ticket.issue_type        = str(result.get("issue_type", "general_support") or "general_support")[:64]
    ticket.final_reply       = str(result.get("reply", result.get("final", "")) or "")[:8000]
    ticket.internal_note     = str((output.get("internal_note") or ""))[:2000]
    ticket.action            = action
    ticket.amount            = float(result.get("amount", 0) or 0)
    ticket.confidence        = float(result.get("confidence", 0) or 0)
    ticket.quality           = float(result.get("quality", 0) or 0)
    ticket.requires_approval = int(bool(decision.get("requires_approval", False)))
    ticket.approved          = 0
    ticket.urgency           = _clamp(triage.get("urgency", 0),           0, 99)
    ticket.churn_risk        = _clamp(triage.get("churn_risk", 0),        0, 99)
    ticket.refund_likelihood = _clamp(triage.get("refund_likelihood", 0), 0, 99)
    ticket.abuse_likelihood  = _clamp(triage.get("abuse_likelihood", 0),  0, 99)
    ticket.complexity        = _clamp(triage.get("complexity", 0),        0, 99)

    db.commit()
    db.refresh(ticket)
    return ticket


def log_action(
    db: Session,
    *,
    username: str,
    ticket_id: int | None = None,
    action: str,
    amount: float,
    issue_type: str,
    reason: str,
    status: str,
    confidence: float,
    quality: float,
    message_snippet: str,
    requires_approval: bool = False,
    approved: bool = False,
) -> ActionLog:
    """
    Write an immutable ActionLog row.
    ticket_id FK enables exact Ticket lookup during approval — no fuzzy matching.
    """
    entry = ActionLog(
        timestamp         = _now_iso(),
        username          = username,
        ticket_id         = ticket_id,
        action            = action,
        amount            = round(float(amount or 0), 2),
        issue_type        = issue_type,
        reason            = (reason or "")[:500],
        status            = status,
        confidence        = round(float(confidence or 0), 4),
        quality           = round(float(quality or 0), 4),
        message_snippet   = (message_snippet or "")[:200],
        requires_approval = int(requires_approval),
        approved          = int(approved),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# =============================================================================
# 9. SERIALIZATION HELPERS
# =============================================================================


def serialize_ticket(ticket: Ticket) -> dict[str, Any]:
    """Full ticket shape for inbox UI and frontend consumption."""
    return {
        "id":               ticket.id,
        "created_at":       ticket.created_at,
        "updated_at":       ticket.updated_at,
        "username":         ticket.username,
        "channel":          ticket.channel,
        "source":           ticket.source,
        "status":           ticket.status,
        "queue":            ticket.queue,
        "priority":         ticket.priority,
        "risk_level":       ticket.risk_level,
        "issue_type":       ticket.issue_type,
        "subject":          ticket.subject,
        "customer_message": ticket.customer_message,
        "final_reply":      ticket.final_reply,
        "internal_note":    ticket.internal_note,
        "action":           ticket.action,
        "amount":           ticket.amount,
        "confidence":       ticket.confidence,
        "quality":          ticket.quality,
        "requires_approval":bool(ticket.requires_approval),
        "approved":         bool(ticket.approved),
        "urgency":          ticket.urgency,
        "churn_risk":       ticket.churn_risk,
        "refund_likelihood":ticket.refund_likelihood,
        "abuse_likelihood": ticket.abuse_likelihood,
        "complexity":       ticket.complexity,
    }


def serialize_ticket_with_log(ticket: Ticket, db: Session) -> dict[str, Any]:
    """
    Extended ticket serialization — includes the most recent ActionLog entry.
    Used by GET /tickets/{id} for a richer inbox detail view.
    """
    base = serialize_ticket(ticket)
    log  = (
        db.query(ActionLog)
        .filter(ActionLog.ticket_id == ticket.id)
        .order_by(ActionLog.id.desc())
        .first()
    )
    if log:
        base["action_log"] = {
            "log_id":           log.id,
            "action":           log.action,
            "amount":           log.amount,
            "status":           log.status,
            "reason":           log.reason,
            "confidence":       log.confidence,
            "quality":          log.quality,
            "requires_approval":bool(log.requires_approval),
            "approved":         bool(log.approved),
            "timestamp":        log.timestamp,
        }
    else:
        base["action_log"] = None
    return base


def serialize_support_result(result: dict[str, Any], user: User) -> dict[str, Any]:
    """
    Canonical response shape for every support call.
    Keys are stable — the frontend depends on these.
    """
    usage_summary = get_usage_summary(user)
    tool_result   = result.get("tool_result") or {}
    impact        = result.get("impact")      or {}

    return {
        # Core reply — frontend reads result.reply
        "reply":        result.get("response", result.get("final", "No response")),
        "mode":         result.get("mode", "unknown"),
        "quality":      result.get("quality", 0),
        "confidence":   result.get("confidence", 0),
        "action":       result.get("action", "none"),
        "amount":       result.get("amount", 0),
        "reason":       result.get("reason", ""),
        "issue_type":   result.get("issue_type", "general_support"),
        "order_status": result.get("order_status", "unknown"),
        # Execution detail
        "tool_result":  tool_result,
        "tool_status":  result.get("tool_status", tool_result.get("status", "unknown")),
        "impact":       impact,
        # Decision metadata — action visibility UI
        "decision":     result.get("decision", {}),
        "output":       result.get("output", {}),
        "meta":         result.get("meta", {}),
        "triage":       result.get("triage", {}),
        "history":      result.get("history", {}),
        # Plan / usage — frontend reads to update plan bar
        "tier":         usage_summary["tier"],
        "plan_limit":   usage_summary["limit"],
        "usage":        usage_summary["usage"],
        "remaining":    max(
            0,
            get_plan_config(get_public_plan_name(user))["monthly_limit"] - usage_summary["usage"],
        ),
    }

# =============================================================================
# 10. BILLING HELPERS (STRIPE)
# =============================================================================


def safe_refund_reason(value: str | None) -> str:
    text = (value or "").strip().lower()
    return (
        text
        if text in {"duplicate", "fraudulent", "requested_by_customer"}
        else "requested_by_customer"
    )


def cents_from_dollars(amount: Any) -> int:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return int(round(min(max(value, 0), MAX_AUTO_REFUND) * 100))


def dollars_from_cents(cents: int) -> float:
    return int(cents) / 100


def rewrite_refund_failure_message(reason: str) -> str:
    return (
        "I've opened this for manual review because I couldn't complete the refund automatically. "
        + reason
    ).strip()


def get_charge_context(
    *,
    payment_intent_id: str | None,
    charge_id: str | None,
) -> dict[str, Any]:
    pi  = (payment_intent_id or "").strip()
    cid = (charge_id or "").strip()

    if pi:
        intent  = stripe.PaymentIntent.retrieve(pi)
        charges = (intent.get("charges") or {}).get("data") or []
        if not charges:
            raise Exception("No charge found for this payment_intent.")
        charge = charges[0]
        return {
            "payment_intent_id": pi,
            "charge_id":         charge.get("id", ""),
            "charge_amount":     int(charge.get("amount", 0) or 0),
            "currency":          str(charge.get("currency", "usd") or "usd").upper(),
            "captured":          bool(charge.get("captured", True)),
            "refunded":          bool(charge.get("refunded", False)),
            "amount_refunded":   int(charge.get("amount_refunded", 0) or 0),
        }

    if cid:
        charge = stripe.Charge.retrieve(cid)
        return {
            "payment_intent_id": str(charge.get("payment_intent", "") or ""),
            "charge_id":         cid,
            "charge_amount":     int(charge.get("amount", 0) or 0),
            "currency":          str(charge.get("currency", "usd") or "usd").upper(),
            "captured":          bool(charge.get("captured", True)),
            "refunded":          bool(charge.get("refunded", False)),
            "amount_refunded":   int(charge.get("amount_refunded", 0) or 0),
        }

    raise Exception("A payment_intent_id or charge_id is required for an automatic refund.")


def evaluate_refund_rules(
    *,
    result: dict[str, Any],
    user: User,
    charge_context: dict[str, Any],
    requested_cents: int,
    refund_cents: int,
) -> dict[str, Any]:
    tier         = get_plan_name(user)
    issue_type   = str(result.get("issue_type", "general_support") or "general_support").strip().lower()
    order_status = str(result.get("order_status", "unknown") or "unknown").strip().lower()
    confidence   = float(result.get("confidence", 0) or 0)
    quality      = float(result.get("quality",    0) or 0)

    checks: list[dict[str, Any]] = []

    def _rule(name: str, passed: bool, detail: str) -> None:
        checks.append({"rule": name, "passed": passed, "detail": detail})

    _rule("enabled",            REFUND_RULES["enabled"],
          "Auto refunds enabled" if REFUND_RULES["enabled"] else "Auto refunds disabled")
    _rule("allowed_tier",       tier in REFUND_RULES["allowed_tiers"],
          f"Tier '{tier}' {'allowed' if tier in REFUND_RULES['allowed_tiers'] else 'not allowed'}")
    _rule("allowed_issue_type", issue_type in REFUND_RULES["allowed_issue_types"],
          f"Issue type '{issue_type}' {'allowed' if issue_type in REFUND_RULES['allowed_issue_types'] else 'not allowed'}")
    _rule("order_status_ok",    order_status not in REFUND_RULES["blocked_order_statuses"],
          f"Order status '{order_status}' acceptable")
    _rule("min_confidence",     confidence >= REFUND_RULES["min_confidence"],
          f"Confidence {confidence:.2f} >= {REFUND_RULES['min_confidence']:.2f}")
    _rule("min_quality",        quality >= REFUND_RULES["min_quality"],
          f"Quality {quality:.2f} >= {REFUND_RULES['min_quality']:.2f}")

    charge_amount   = int(charge_context["charge_amount"])
    amount_refunded = int(charge_context.get("amount_refunded", 0) or 0)
    remaining       = max(0, charge_amount - amount_refunded)

    _rule("captured",         bool(charge_context.get("captured", False)),
          "Charge is captured")
    _rule("has_refundable",   remaining > 0,
          f"Remaining refundable: ${dollars_from_cents(remaining):.2f}")
    _rule("within_cap",       dollars_from_cents(refund_cents) <= REFUND_RULES["max_auto_refund_amount"],
          f"${dollars_from_cents(refund_cents):.2f} <= cap ${REFUND_RULES['max_auto_refund_amount']:.2f}")
    _rule("positive_request", requested_cents > 0,
          f"Requested: ${dollars_from_cents(requested_cents):.2f}")
    _rule("positive_refund",  refund_cents > 0,
          f"Actual: ${dollars_from_cents(refund_cents):.2f}")

    blocked = [r for r in checks if not r["passed"]]
    return {
        "allowed":                     len(blocked) == 0,
        "blocked_rules":               blocked,
        "all_rules":                   checks,
        "tier":                        tier,
        "issue_type":                  issue_type,
        "order_status":                order_status,
        "confidence":                  confidence,
        "quality":                     quality,
        "requested_amount":            dollars_from_cents(requested_cents),
        "charge_amount":               dollars_from_cents(charge_amount),
        "remaining_refundable_amount": dollars_from_cents(remaining),
        "refund_amount":               dollars_from_cents(refund_cents),
    }


def execute_real_refund(
    *,
    amount: int,
    payment_intent_id: str | None,
    charge_id: str | None,
    refund_reason: str | None,
    username: str,
    issue_type: str,
    user: User,
    result: dict[str, Any],
) -> dict[str, Any]:
    pi  = (payment_intent_id or "").strip()
    cid = (charge_id or "").strip()

    if not STRIPE_KEY:
        return {"ok": False, "status": "stripe_not_configured", "detail": "Stripe not configured."}
    if not pi and not cid:
        return {"ok": False, "status": "missing_payment_reference", "detail": "payment_intent_id or charge_id required."}

    cents_requested = cents_from_dollars(amount)
    if cents_requested <= 0:
        return {"ok": False, "status": "invalid_refund_amount", "detail": "Refund amount must be > 0."}

    try:
        ctx              = get_charge_context(payment_intent_id=pi, charge_id=cid)
        charge_amount    = int(ctx["charge_amount"])
        already_refunded = int(ctx.get("amount_refunded", 0) or 0)
        remaining        = max(0, charge_amount - already_refunded)

        if remaining <= 0:
            return {"ok": False, "status": "no_refundable_balance",
                    "detail": "No refundable balance remaining.", "charge_context": ctx}

        refund_cents  = min(cents_requested, remaining)
        rules_summary = evaluate_refund_rules(
            result=result, user=user, charge_context=ctx,
            requested_cents=cents_requested, refund_cents=refund_cents,
        )

        if not rules_summary["allowed"]:
            blocked_details = "; ".join(r["detail"] for r in rules_summary["blocked_rules"])
            return {"ok": False, "status": "refund_blocked_by_rules",
                    "detail": blocked_details or "Blocked by rules.",
                    "rules_summary": rules_summary, "charge_context": ctx}

        payload: dict[str, Any] = {
            "amount": refund_cents,
            "reason": safe_refund_reason(refund_reason),
            "metadata": {
                "source":                  "xalvion",
                "username":                username,
                "issue_type":              issue_type,
                "requested_refund_cents":  str(cents_requested),
                "charge_amount_cents":     str(charge_amount),
                "rule_tier":               rules_summary["tier"],
            },
        }
        if pi:
            payload["payment_intent"] = pi
        else:
            payload["charge"] = cid

        refund        = stripe.Refund.create(**payload)
        refund_amount = int(getattr(refund, "amount", refund_cents) or refund_cents) / 100

        return {
            "ok": True, "status": "refunded",
            "refund_id":                   getattr(refund, "id", ""),
            "amount":                      refund_amount,
            "currency":                    ctx["currency"],
            "payment_intent_id":           ctx["payment_intent_id"] or pi,
            "charge_id":                   ctx["charge_id"] or cid,
            "requested_amount":            cents_requested / 100,
            "charge_amount":               charge_amount / 100,
            "remaining_refundable_amount": remaining / 100,
            "capped":                      refund_cents < cents_requested,
            "rules_summary":               rules_summary,
            "charge_context":              ctx,
        }
    except Exception as exc:
        return {"ok": False, "status": "stripe_refund_failed", "detail": str(exc)}


def apply_real_actions(result: dict[str, Any], req: SupportRequest, user: User) -> dict[str, Any]:
    result = dict(result or {})
    if str(result.get("action", "none") or "none").lower() != "refund":
        return result

    refund_result = execute_real_refund(
        amount            = int(result.get("amount", 0) or 0),
        payment_intent_id = req.payment_intent_id,
        charge_id         = req.charge_id,
        refund_reason     = req.refund_reason,
        username          = str(getattr(user, "username", "unknown") or "unknown"),
        issue_type        = str(result.get("issue_type", "general_support") or "general_support"),
        user              = user,
        result            = result,
    )

    if refund_result.get("ok"):
        refunded_amount  = refund_result.get("amount", result.get("amount", 0))
        requested_amount = refund_result.get("requested_amount", refunded_amount)
        capped           = bool(refund_result.get("capped", False))
        result["action"]      = "refund"
        result["amount"]      = refunded_amount
        result["reason"]      = (
            f"Refund capped to ${refunded_amount:.2f}" if capped
            else "Refund processed via Stripe"
        )
        result["tool_status"] = "refunded"
        result["tool_result"] = refund_result
        result["impact"]      = {"type": "refund", "amount": refunded_amount}
        if capped:
            result["response"] = (
                f"I've processed the refund. Requested ${requested_amount:.2f} but "
                f"refundable was ${refunded_amount:.2f} — refunded the full available balance."
            )
            result["final"] = result["response"]
        return result

    failure           = str(refund_result.get("detail", "Automatic refund failed.")).strip()
    result["action"]      = "review"
    result["amount"]      = 0
    result["reason"]      = failure
    result["tool_status"] = refund_result.get("status", "refund_failed")
    result["tool_result"] = refund_result
    result["impact"]      = {"type": "saved", "amount": 0}
    result["response"]    = rewrite_refund_failure_message(failure)
    result["final"]       = result["response"]
    return result


def validate_upgrade_request(desired: str, current_tier: str) -> None:
    if desired not in {"pro", "elite"}:
        raise HTTPException(status_code=400, detail="Invalid tier")
    normalized_current = current_tier if current_tier in PUBLIC_PLAN_TIERS else "free"
    if normalized_current == desired:
        raise HTTPException(status_code=400, detail=f"Already on {desired}")
    if normalized_current == "elite" and desired == "pro":
        raise HTTPException(status_code=400, detail="Downgrades not supported")


def create_checkout_session_for_user(user: User, desired: str) -> Any:
    if not STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    price_id = PRICE_MAP.get(desired, "")
    if not price_id:
        raise HTTPException(status_code=500, detail=f"No Stripe price configured for {desired}")
    try:
        session = stripe.checkout.Session.create(
            mode           = "subscription",
            line_items     = [{"price": price_id, "quantity": 1}],
            success_url    = CHECKOUT_SUCCESS_URL,
            cancel_url     = CHECKOUT_CANCEL_URL,
            metadata       = {"username": user.username, "tier": desired},
            subscription_data = {"metadata": {"username": user.username, "tier": desired}},
            client_reference_id = user.username,
        )
        print(
            f"[STRIPE] checkout created session_id={getattr(session, 'id', None)!r} "
            f"user={user.username!r} tier={desired!r}"
        )
    except Exception as exc:
        print(f"[STRIPE] checkout failed user={user.username!r} tier={desired!r} error={exc}")
        raise HTTPException(status_code=500, detail=f"Stripe checkout error: {exc}") from exc
    return session


def apply_successful_upgrade(db: Session, username: str, tier: str) -> User | None:
    print(f"[STRIPE] apply_successful_upgrade username={username!r} tier={tier!r}")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"[STRIPE] user not found: {username!r}")
        return None
    desired = (tier or "").strip().lower()
    if desired not in {"pro", "elite"}:
        print(f"[STRIPE] invalid tier: {desired!r}")
        return user
    user.tier = desired
    db.commit()
    db.refresh(user)
    print(f"[STRIPE] upgraded {user.username!r} → {user.tier!r}")
    return user


def infer_tier_from_checkout_session(session_id: str) -> str:
    if not session_id or not STRIPE_KEY:
        return ""
    try:
        items = stripe.checkout.Session.list_line_items(session_id, limit=10)
        for item in (getattr(items, "data", None) or []):
            price_id = getattr(getattr(item, "price", None), "id", None) or ""
            if price_id == STRIPE_PRICE_PRO:
                return "pro"
            if price_id == STRIPE_PRICE_ELITE:
                return "elite"
    except Exception as exc:
        print(f"[STRIPE] line item lookup failed session_id={session_id!r} error={exc}")
    return ""

# =============================================================================
# 11. SUPPORT PIPELINE
# =============================================================================


def check_requires_approval(action: str, amount: float) -> bool:
    if not LIVE_MODE:
        return False
    return action == "refund" and float(amount or 0) > APPROVAL_THRESHOLD


def run_support(req: SupportRequest, user: User, db: Session) -> dict[str, Any]:
    """
    Full support pipeline:
      1. Enforce plan limits + rate limit
      2. Create Ticket (traceable from this point on)
      3. Run agent → structured result
      4. Apply approval gate OR real Stripe action
      5. Write result back to Ticket (enum-validated)
      6. Write ActionLog with explicit ticket_id FK
      7. Increment usage counter
      8. Return canonical serialized response

    Safe failure path: any exception marks the Ticket as failed/escalated
    and returns a clean user-facing message. Internal detail is never exposed.
    """
    enforce_plan_limits(user)
    ticket = create_ticket_record(db, user, req)

    try:
        result = run_agent(
            req.message,
            user_id=user.username,
            meta=build_agent_meta(req, user, db),
        )

        action = str(result.get("action", "none") or "none").lower()
        amount = float(result.get("amount", 0) or 0)
        needs_approval = (
            check_requires_approval(action, amount)
            or bool((result.get("decision") or {}).get("requires_approval", False))
        )

        if needs_approval:
            result["action"]      = "review"
            result["amount"]      = 0
            result["reason"]      = (
                f"Refund ${amount:.2f} exceeds approval threshold "
                f"${APPROVAL_THRESHOLD:.2f}. Manual approval required."
            )
            result["response"]    = (
                "I've flagged this refund for manual approval. "
                "Your team will review and process it shortly."
            )
            result["final"]       = result["response"]
            result["reply"]       = result["response"]
            result["tool_status"] = "pending_approval"
            result.setdefault("decision", {}).update({
                "requires_approval": True,
                "queue":             "refund_risk",
                "priority":          "high",
                "risk_level":        "high",
            })
        else:
            result = apply_real_actions(result, req, user)

        update_ticket_from_result(db, ticket, result)

        log_action(
            db,
            username          = str(getattr(user, "username", "unknown")),
            ticket_id         = ticket.id,
            action            = str(result.get("action", "none")),
            amount            = float(result.get("amount", 0) or 0),
            issue_type        = str(result.get("issue_type", "general_support")),
            reason            = str(result.get("reason", "")),
            status            = str(result.get("tool_status", "executed")),
            confidence        = float(result.get("confidence", 0) or 0),
            quality           = float(result.get("quality", 0) or 0),
            message_snippet   = (req.message or "")[:200],
            requires_approval = needs_approval,
            approved          = False,
        )

        if hasattr(user, "usage") and getattr(user, "username", "") not in {"dev_user", "guest"}:
            user.usage = int(getattr(user, "usage", 0) or 0) + 1
            db.commit()
            db.refresh(user)

        serialized                  = serialize_support_result(result, user)
        serialized["ticket"]        = serialize_ticket(ticket)
        serialized["operator_mode"] = get_operator_mode(db)
        return serialized

    except HTTPException:
        raise

    except Exception as exc:
        print(f"[run_support] PIPELINE ERROR ticket_id={ticket.id} error={exc}")
        try:
            ticket.status        = "failed"
            ticket.queue         = "escalated"
            ticket.internal_note = f"Pipeline error: {str(exc)[:500]}"
            ticket.updated_at    = _now_iso()
            db.commit()
        except Exception as db_exc:
            print(f"[run_support] could not mark ticket failed: {db_exc}")

        fallback = (
            "I encountered an issue processing your request. "
            "Our team has been notified and will follow up shortly."
        )
        plan = get_plan_name(user)
        return {
            "reply":        fallback,
            "final":        fallback,
            "response":     fallback,
            "action":       "review",
            "amount":       0,
            "reason":       "Pipeline error — escalated for manual review",
            "issue_type":   "general_support",
            "order_status": "unknown",
            "tool_status":  "error",
            "tool_result":  {"status": "error"},
            "impact":       {"type": "saved", "amount": 0},
            "decision":     {"action": "review", "queue": "escalated", "priority": "high"},
            "output":       {"internal_note": f"Error: {str(exc)[:200]}"},
            "meta": {}, "triage": {}, "history": {},
            "mode":         "error",
            "confidence":   0.0,
            "quality":      0.0,
            "tier":         plan,
            "plan_limit":   get_plan_config(plan)["monthly_limit"],
            "usage":        int(getattr(user, "usage", 0) or 0),
            "remaining":    max(
                0,
                get_plan_config(plan)["monthly_limit"] - int(getattr(user, "usage", 0) or 0),
            ),
            "ticket":       serialize_ticket(ticket),
            "operator_mode":"balanced",
        }

# =============================================================================
# 12. STREAMING HELPERS
# =============================================================================


def sse_event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chunk_text(text: str, size: int = STREAM_CHUNK_SIZE) -> list[str]:
    text = text or ""
    return [text[i:i + size] for i in range(0, len(text), size)] if text else [""]


def build_status_sequence(result: dict[str, Any]) -> list[dict[str, str]]:
    seq = [
        {"stage": "reviewing", "label": "Reviewing request"},
        {"stage": "routing",   "label": "Choosing next step"},
    ]
    action = str(result.get("action", "none") or "none")
    label  = {
        "refund": "Confirming refund",
        "credit": "Applying credit",
        "review": "Review in progress",
    }.get(action, "Drafting reply")
    seq.append({
        "stage": "acting" if action in {"refund", "credit", "review"} else "responding",
        "label": label,
    })
    return seq


def stream_support_events(result: dict[str, Any]) -> AsyncIterator[str]:
    async def generator() -> AsyncIterator[str]:
        for item in build_status_sequence(result):
            yield sse_event("status", item)
            await asyncio.sleep(STATUS_STEP_DELAY)
        for part in chunk_text(result.get("reply", ""), STREAM_CHUNK_SIZE):
            yield sse_event("chunk", {"text": part})
            await asyncio.sleep(STREAM_CHUNK_DELAY)
        yield sse_event("result", result)
        yield sse_event("done",   {"ok": True})
    return generator()

# =============================================================================
# 13. ROUTES — STATIC
# =============================================================================


@app.get("/")
def serve_index():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return JSONResponse({"status": "ok", "service": "xalvion-sovereign-brain",
                         "warning": "index.html not found"})


@app.get("/app.js")
def serve_app_js():
    if os.path.exists(APP_JS_PATH):
        return FileResponse(APP_JS_PATH, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/landing")
def serve_landing():
    if os.path.exists(LANDING_PATH):
        return FileResponse(LANDING_PATH)
    raise HTTPException(status_code=404, detail="landing.html not found")

# =============================================================================
# 14. ROUTES — HEALTH
# =============================================================================


@app.get("/health")
def health():
    return {"status": "ok", "service": "xalvion-sovereign-brain"}


@app.get("/health/deep")
def health_deep(db: Session = Depends(get_db)):
    """Deep health check — probes DB and core tables. Used by uptime monitors."""
    from sqlalchemy import text as _text

    checks: dict[str, Any] = {}

    try:
        db.execute(_text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        checks["users"]   = db.query(User).count()
        checks["tickets"] = db.query(Ticket).count()
        checks["actions"] = db.query(ActionLog).count()
    except Exception as exc:
        checks["tables"] = f"error: {exc}"

    try:
        checks["operator_mode"] = get_operator_mode(db)
    except Exception as exc:
        checks["operator_mode"] = f"error: {exc}"

    # Explicit per-key check — avoids operator-precedence bug in all()
    degraded = any(
        isinstance(v, str) and v.startswith("error")
        for v in checks.values()
    )
    checks["status"]  = "degraded" if degraded else "ok"
    checks["service"] = "xalvion-sovereign-brain"
    return checks

# =============================================================================
# 15. ROUTES — AUTH
# =============================================================================


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    usage_summary   = get_usage_summary(user)
    public_username = "" if user.username in {"guest", "dev_user"} else user.username
    public_tier     = get_public_plan_name(user)
    public_plan     = get_plan_config(public_tier)
    public_limit    = int(public_plan["monthly_limit"])
    return {
        "username":         public_username,
        "tier":             public_tier,
        "usage":            usage_summary["usage"],
        "limit":            public_limit,
        "remaining":        max(0, public_limit - usage_summary["usage"]),
        "dashboard_access": public_plan["dashboard_access"],
        "priority_routing": public_plan["priority_routing"],
        "is_dev":           usage_summary["tier"] == "dev" and user.username == ADMIN_USERNAME,
        "is_admin":         user.username == ADMIN_USERNAME,
    }


@app.post("/signup")
def signup(req: AuthRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    password = (req.password or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    if len(username) > 64 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Username or password too long")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    db.add(User(username=username, password=hash_password(password), usage=0, tier="free"))
    db.commit()
    return {"message": "Account created", "tier": "free"}


@app.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    user     = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.username == ADMIN_USERNAME and user.tier != "elite":
        user.tier = "elite"
        db.commit()
        db.refresh(user)
    token         = create_token(user.username)
    usage_summary = get_usage_summary(user)
    return {
        "token":    token,
        "tier":     usage_summary["tier"],
        "usage":    usage_summary["usage"],
        "limit":    usage_summary["limit"],
        "remaining":usage_summary["remaining"],
        "is_admin": user.username == ADMIN_USERNAME,
    }

# =============================================================================
# 16. ROUTES — BILLING & PLANS
# =============================================================================


@app.get("/billing/plans")
def billing_plans(user: User = Depends(get_current_user)):
    return build_upgrade_payload(get_public_plan_name(user))


@app.post("/billing/upgrade")
def upgrade_plan(
    req: UpgradeRequest,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    desired      = (req.tier or "").strip().lower()
    current_tier = get_public_plan_name(user)
    print(
        f"[STRIPE] /billing/upgrade user={getattr(user, 'username', None)!r} "
        f"current={current_tier!r} desired={desired!r}"
    )
    validate_upgrade_request(desired, current_tier)

    if STRIPE_KEY and PRICE_MAP.get(desired):
        session = create_checkout_session_for_user(user, desired)
        return {
            "mode":         "checkout",
            "checkout_url": session.url,
            "session_id":   session.id,
            "tier":         current_tier,
            "usage":        int(getattr(user, "usage", 0) or 0),
            "limit":        get_plan_config(current_tier)["monthly_limit"],
            "remaining":    max(
                0,
                get_plan_config(current_tier)["monthly_limit"]
                - int(getattr(user, "usage", 0) or 0),
            ),
        }

    if not ALLOW_DIRECT_BILLING_BYPASS:
        raise HTTPException(
            status_code=500,
            detail=(
                "Stripe not fully configured. "
                "Set STRIPE_SECRET_KEY and price IDs, "
                "or enable ALLOW_DIRECT_BILLING_BYPASS for local testing."
            ),
        )

    print(f"[STRIPE] direct billing bypass user={user.username!r} desired={desired!r}")
    user.tier = desired
    db.commit()
    db.refresh(user)
    usage_summary = get_usage_summary(user)
    return {
        "mode":     "direct",
        "message":  f"Upgraded to {desired}",
        "tier":     usage_summary["tier"],
        "usage":    usage_summary["usage"],
        "limit":    usage_summary["limit"],
        "remaining":usage_summary["remaining"],
    }


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler.

    Idempotency pattern:
      1. Parse and verify the event.
      2. Check for existing ProcessedWebhook row — return early if duplicate.
      3. INSERT ProcessedWebhook with outcome="processing" BEFORE side effects.
         If the INSERT races, we treat it as a duplicate.
      4. Apply side effects (upgrade, etc.).
      5. Update ProcessedWebhook.outcome to ok | failed | skipped.

    This means every event is either processed exactly once or safely skipped.
    Failures are auditable via the processed_webhooks table.
    """
    if not STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    print(f"[STRIPE] webhook received bytes={len(payload)} has_sig={bool(sig_header)}")

    try:
        event = (
            stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
            if STRIPE_WEBHOOK_SECRET
            else stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
        )
    except Exception as exc:
        print(f"[STRIPE] webhook parse failed: {exc}")
        raise HTTPException(status_code=400, detail=f"Webhook parse failed: {exc}") from exc

    event_type  = str(getattr(event, "type",  "") or "")
    event_data  = getattr(event, "data",   None)
    data_object = getattr(event_data, "object", None)
    event_id    = str(getattr(event, "id",   "") or "")

    print(f"[STRIPE] event_type={event_type!r} event_id={event_id!r}")

    # ── Idempotency: claim before side effects ────────────────────────────
    if event_id:
        existing = (
            db.query(ProcessedWebhook)
            .filter(ProcessedWebhook.event_id == event_id)
            .first()
        )
        if existing:
            print(f"[STRIPE] duplicate skipped event_id={event_id!r} prior_outcome={existing.outcome!r}")
            return {"received": True, "type": event_type, "duplicate": True}

        try:
            db.add(ProcessedWebhook(
                event_id     = event_id,
                event_type   = event_type,
                processed_at = _now_iso(),
                outcome      = "processing",
            ))
            db.commit()
        except Exception as claim_exc:
            # Concurrent INSERT — another worker claimed it first
            print(f"[STRIPE] claim race event_id={event_id!r}: {claim_exc}")
            db.rollback()
            return {"received": True, "type": event_type, "duplicate": True}

    # ── Process event ─────────────────────────────────────────────────────
    outcome = "ok"
    detail  = ""

    try:
        if event_type == "checkout.session.completed":
            metadata = getattr(data_object, "metadata", None) or {}
            if not isinstance(metadata, dict):
                try:
                    metadata = dict(metadata)
                except Exception:
                    metadata = {}

            client_reference_id = getattr(data_object, "client_reference_id", None) or ""
            session_id          = getattr(data_object, "id", None)
            username            = (metadata.get("username") or client_reference_id or "").strip()
            tier                = (metadata.get("tier") or "").strip().lower()

            if not tier and session_id:
                tier = infer_tier_from_checkout_session(session_id)
                print(f"[STRIPE] inferred tier from line items: {tier!r}")

            print(
                f"[STRIPE] checkout.session.completed "
                f"username={username!r} tier={tier!r} "
                f"metadata={metadata!r} session_id={session_id!r}"
            )

            if username and tier:
                upgraded_user = apply_successful_upgrade(db, username, tier)
                if upgraded_user:
                    print(f"[STRIPE] upgrade applied: {upgraded_user.username!r} → {upgraded_user.tier!r}")
                else:
                    outcome = "skipped"
                    detail  = f"User not found: {username!r}"
                    print(f"[STRIPE] upgrade skipped — user not found: {username!r}")
            else:
                outcome = "skipped"
                detail  = "Missing username or tier in event payload"
                print(f"[STRIPE] upgrade skipped — {detail}")

        elif event_type in {"customer.subscription.deleted", "customer.subscription.updated"}:
            # Log subscription lifecycle events for future handling
            print(f"[STRIPE] subscription lifecycle: {event_type!r}")

        else:
            print(f"[STRIPE] unhandled event type: {event_type!r}")

    except Exception as process_exc:
        print(f"[STRIPE] processing error event_id={event_id!r}: {process_exc}")
        outcome = "failed"
        detail  = str(process_exc)[:500]

    # ── Update claim record with final outcome ────────────────────────────
    if event_id:
        try:
            record = (
                db.query(ProcessedWebhook)
                .filter(ProcessedWebhook.event_id == event_id)
                .first()
            )
            if record:
                record.outcome = outcome
                record.detail  = detail
                db.commit()
        except Exception as update_exc:
            print(f"[STRIPE] could not update webhook record: {update_exc}")

    return {"received": True, "type": event_type, "outcome": outcome}

# =============================================================================
# 17. ROUTES — DASHBOARD & METRICS
# =============================================================================


@app.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Operational dashboard. All numbers come from persisted DB data.
    Analytics file metrics (avg_confidence/quality) fall back to DB
    aggregates when the analytics module is unavailable or returns zeros.
    """
    file_metrics = get_metrics() or {}

    # ── Ticket counts ─────────────────────────────────────────────────────
    total_tickets = db.query(Ticket).count()
    auto_resolved = db.query(Ticket).filter(Ticket.status == "resolved").count()
    escalated     = db.query(Ticket).filter(Ticket.status.in_(["waiting", "escalated"])).count()
    failed_count  = db.query(Ticket).filter(Ticket.status == "failed").count()
    high_risk     = db.query(Ticket).filter(Ticket.churn_risk >= 60).count()
    pending_approvals = db.query(ActionLog).filter(
        ActionLog.requires_approval == 1, ActionLog.approved == 0
    ).count()

    # ── Financial aggregates (DB-level SUM — no row loading) ──────────────
    refund_total = float(
        db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "refund").scalar() or 0
    )
    credit_total = float(
        db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "credit").scalar() or 0
    )
    actions_done = db.query(ActionLog).filter(
        ActionLog.action.in_(["refund", "credit"])
    ).count()
    approved_count = db.query(ActionLog).filter(ActionLog.approved == 1).count()

    # ── Confidence / quality — DB fallback when analytics file is stale ───
    db_avg_conf = float(
        db.query(func.avg(ActionLog.confidence)).filter(ActionLog.confidence > 0).scalar() or 0
    )
    db_avg_qual = float(
        db.query(func.avg(ActionLog.quality)).filter(ActionLog.quality > 0).scalar() or 0
    )
    avg_confidence = file_metrics.get("avg_confidence") or round(db_avg_conf, 4)
    avg_quality    = file_metrics.get("avg_quality")    or round(db_avg_qual, 4)

    # ── Ticket breakdowns (GROUP BY — no row loading) ─────────────────────
    queue_rows = db.query(Ticket.queue,    func.count(Ticket.id)).group_by(Ticket.queue).all()
    prio_rows  = db.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    risk_rows  = db.query(Ticket.risk_level, func.count(Ticket.id)).group_by(Ticket.risk_level).all()
    status_rows= db.query(Ticket.status,  func.count(Ticket.id)).group_by(Ticket.status).all()

    by_queue    = {_safe_queue(q    or "new"):    int(c) for q, c in queue_rows}
    by_priority = {_safe_priority(p or "medium"): int(c) for p, c in prio_rows}
    by_risk     = {_safe_risk(r     or "medium"): int(c) for r, c in risk_rows}
    by_status   = {_safe_status(s   or "new"):    int(c) for s, c in status_rows}

    usage_summary = get_usage_summary(user)
    public_tier   = get_public_plan_name(user)

    return {
        # Quality metrics
        "total_interactions":   file_metrics.get("total_interactions", 0),
        "avg_confidence":       avg_confidence,
        "avg_quality":          avg_quality,
        # Ticket operations
        "total_tickets":        total_tickets,
        "auto_resolved":        auto_resolved,
        "escalated":            escalated,
        "failed":               failed_count,
        "high_churn_risk":      high_risk,
        "pending_approvals":    pending_approvals,
        "approved_actions":     approved_count,
        "auto_resolution_rate": round(auto_resolved / max(1, total_tickets) * 100, 2),
        "escalation_rate":      round(escalated    / max(1, total_tickets) * 100, 2),
        # Financial
        "refund_total":         round(refund_total, 2),
        "credit_total":         round(credit_total, 2),
        "money_saved":          round(refund_total + credit_total, 2),
        "actions":              actions_done,
        # Breakdowns
        "by_queue":             by_queue,
        "by_priority":          by_priority,
        "by_risk":              by_risk,
        "by_status":            by_status,
        # Current user plan
        "your_usage":           usage_summary["usage"],
        "your_tier":            public_tier,
        "your_limit":           get_plan_config(public_tier)["monthly_limit"],
        "remaining":            usage_summary["remaining"],
        "dashboard_access":     get_plan_config(public_tier)["dashboard_access"],
        "priority_routing":     get_plan_config(public_tier)["priority_routing"],
        "operator_mode":        get_operator_mode(db),
        # Platform (admin-useful)
        "total_users":          db.query(User).count(),
        "pro_users":            db.query(User).filter(User.tier == "pro").count(),
        "elite_users":          db.query(User).filter(User.tier == "elite").count(),
    }

# =============================================================================
# 18. ROUTES — TICKETS
# =============================================================================


@app.get("/tickets")
def list_tickets(
    limit:      int = 50,
    offset:     int = 0,
    page:       int | None = None,       # alias for offset-based paging
    page_size:  int | None = None,       # alias for limit
    queue:      str | None = None,
    status:     str | None = None,
    priority:   str | None = None,
    risk_level: str | None = None,
    issue_type: str | None = None,
    username:   str | None = None,       # admin filter by user
    search:     str | None = None,
    sort:       str = "newest",
    user: User = Depends(get_current_user),
    db:   Session = Depends(get_db),
):
    """
    Full ticket inbox with filtering, search, pagination, and sort.

    Pagination: use limit+offset OR page+page_size (page is 1-indexed).
    Sort: newest | oldest | urgency | churn_risk | priority
    Filters: queue, status, priority, risk_level, issue_type, username (admin)
    Search: full-text across subject, message, reply, notes, issue_type
    """
    from sqlalchemy import case as _case

    # Resolve page/page_size aliases
    if page_size is not None:
        limit = page_size
    if page is not None:
        offset = max(0, (page - 1)) * max(1, limit)

    q = db.query(Ticket)

    is_admin = getattr(user, "username", "") == ADMIN_USERNAME

    # Scope: non-admins see only their own tickets
    if not is_admin:
        q = q.filter(Ticket.username == user.username)
    elif username:
        # Admin can filter by a specific user
        q = q.filter(Ticket.username == username.strip())

    # Validated filters
    if queue:
        q = q.filter(Ticket.queue == _safe_queue(queue))
    if status:
        q = q.filter(Ticket.status == _safe_status(status))
    if priority:
        q = q.filter(Ticket.priority == _safe_priority(priority))
    if risk_level:
        q = q.filter(Ticket.risk_level == _safe_risk(risk_level))
    if issue_type:
        q = q.filter(Ticket.issue_type == issue_type.strip().lower()[:64])

    # Full-text search
    if search and len(search.strip()) >= 2:
        term = f"%{search.strip()}%"
        q = q.filter(
            Ticket.subject.ilike(term)
            | Ticket.customer_message.ilike(term)
            | Ticket.final_reply.ilike(term)
            | Ticket.internal_note.ilike(term)
            | Ticket.issue_type.ilike(term)
        )

    # Sort
    sort_map = {
        "newest":     Ticket.id.desc(),
        "oldest":     Ticket.id.asc(),
        "urgency":    Ticket.urgency.desc(),
        "churn_risk": Ticket.churn_risk.desc(),
        "priority":   _case(
            (Ticket.priority == "high",   3),
            (Ticket.priority == "medium", 2),
            (Ticket.priority == "low",    1),
            else_=0,
        ).desc(),
    }
    q = q.order_by(sort_map.get(sort, Ticket.id.desc()))

    # Pagination
    total     = q.count()
    limit     = max(1, min(limit, 200))
    offset    = max(0, offset)
    rows      = q.offset(offset).limit(limit).all()
    curr_page = (offset // limit) + 1 if limit > 0 else 1

    return {
        "operator_mode": get_operator_mode(db),
        "total":         total,
        "limit":         limit,
        "offset":        offset,
        "page":          curr_page,
        "page_size":     limit,
        "has_more":      (offset + limit) < total,
        "items":         [serialize_ticket(r) for r in rows],
        # Backward-compat alias
        "tickets":       [serialize_ticket(r) for r in rows],
    }


@app.get("/tickets/queues")
def ticket_queue_counts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue + status counts via SQL GROUP BY — never loads full rows into memory."""
    is_admin = getattr(user, "username", "") == ADMIN_USERNAME

    base_q = db.query(Ticket.queue, func.count(Ticket.id).label("cnt"))
    if not is_admin:
        base_q = base_q.filter(Ticket.username == user.username)
    queue_counts: dict[str, int] = {q: 0 for q in VALID_QUEUES}
    for qname, cnt in base_q.group_by(Ticket.queue).all():
        queue_counts[_safe_queue(qname or "new")] = int(cnt)

    base_s = db.query(Ticket.status, func.count(Ticket.id).label("cnt"))
    if not is_admin:
        base_s = base_s.filter(Ticket.username == user.username)
    status_counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    for sname, cnt in base_s.group_by(Ticket.status).all():
        status_counts[_safe_status(sname or "new")] = int(cnt)

    return {
        "queues":        queue_counts,
        "statuses":      status_counts,
        "operator_mode": get_operator_mode(db),
    }


@app.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns full ticket detail including most recent action log entry."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if getattr(user, "username", "") != ADMIN_USERNAME and ticket.username != user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    return serialize_ticket_with_log(ticket, db)


@app.post("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    req: TicketStatusRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only — mutate ticket status/queue/priority/note. All enum-validated."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if req.status:
        ticket.status   = _safe_status(req.status,   ticket.status)
    if req.queue:
        ticket.queue    = _safe_queue(req.queue,     ticket.queue)
    if req.priority:
        ticket.priority = _safe_priority(req.priority, ticket.priority)
    if req.internal_note:
        existing             = (ticket.internal_note or "").strip()
        addition             = (req.internal_note or "").strip()
        ticket.internal_note = (existing + "\n" + addition).strip() if existing else addition

    ticket.updated_at = _now_iso()
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(ticket)

# =============================================================================
# 19. ROUTES — ADMIN
# =============================================================================


@app.post("/admin/reset-usage")
def admin_reset_usage(
    req: AdminUserAction,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.username == req.username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.usage = 0
    db.commit()
    return {"message": f"Usage reset for {req.username}"}


@app.get("/admin/users")
def admin_list_users(
    limit:  int = 200,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Returns paginated user list. Limit capped at 500 to prevent accidental full dumps."""
    limit  = max(1, min(limit, 500))
    offset = max(0, offset)
    total  = db.query(User).count()
    users  = db.query(User).order_by(User.username.asc()).offset(offset).limit(limit).all()
    return {
        "total":    total,
        "limit":    limit,
        "offset":   offset,
        "has_more": (offset + limit) < total,
        "users":    [{"username": u.username, "tier": u.tier, "usage": u.usage} for u in users],
    }


@app.post("/admin/set-tier")
def admin_set_tier(
    req: AdminUserAction,
    tier: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if tier not in {"free", "pro", "elite"}:
        raise HTTPException(status_code=400, detail="Invalid tier")
    target = db.query(User).filter(User.username == req.username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.tier = tier
    db.commit()
    return {"message": f"{req.username} set to {tier}"}


@app.get("/admin/action-logs")
def admin_action_logs(
    limit:    int = 100,
    offset:   int = 0,
    username: str | None = None,
    action:   str | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated action log with optional user/action filters."""
    limit  = max(1, min(limit, 500))
    offset = max(0, offset)
    q      = db.query(ActionLog)
    if username:
        q = q.filter(ActionLog.username == username.strip())
    if action:
        q = q.filter(ActionLog.action == action.strip().lower())
    total = q.count()
    logs  = q.order_by(ActionLog.id.desc()).offset(offset).limit(limit).all()
    return {
        "total":    total,
        "limit":    limit,
        "offset":   offset,
        "has_more": (offset + limit) < total,
        "logs": [
            {
                "id":                log.id,
                "timestamp":         log.timestamp,
                "username":          log.username,
                "ticket_id":         log.ticket_id,
                "action":            log.action,
                "amount":            log.amount,
                "issue_type":        log.issue_type,
                "reason":            log.reason,
                "status":            log.status,
                "confidence":        log.confidence,
                "quality":           log.quality,
                "message_snippet":   log.message_snippet,
                "requires_approval": bool(log.requires_approval),
                "approved":          bool(log.approved),
            }
            for log in logs
        ],
    }


@app.get("/admin/pending-approvals")
def admin_pending_approvals(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    pending = (
        db.query(ActionLog)
        .filter(ActionLog.requires_approval == 1, ActionLog.approved == 0)
        .order_by(ActionLog.id.desc())
        .all()
    )
    return [
        {
            "id":              log.id,
            "timestamp":       log.timestamp,
            "username":        log.username,
            "ticket_id":       log.ticket_id,
            "action":          log.action,
            "amount":          log.amount,
            "issue_type":      log.issue_type,
            "reason":          log.reason,
            "message_snippet": log.message_snippet,
        }
        for log in pending
    ]


@app.post("/admin/approve/{log_id}")
def admin_approve_action(
    log_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Approve a pending action.

    Uses ActionLog.ticket_id (explicit FK) to find the exact Ticket —
    no fuzzy matching, no drift possible. Both records updated atomically
    in one db.commit().
    """
    log = db.query(ActionLog).filter(ActionLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if log.approved:
        raise HTTPException(status_code=400, detail="Already approved")

    log.approved = 1
    log.status   = "approved"

    # Sync the exact Ticket using the explicit FK
    ticket = None
    if log.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == log.ticket_id).first()
        if ticket:
            ticket.approved      = 1
            ticket.status        = _safe_status("resolved")
            ticket.queue         = _safe_queue("resolved")
            ticket.updated_at    = _now_iso()
            existing_note        = (ticket.internal_note or "").strip()
            approval_note        = f"Approved by {admin.username} at {_now_iso()}"
            ticket.internal_note = (
                (existing_note + "\n" + approval_note).strip()
                if existing_note
                else approval_note
            )
            print(f"[APPROVE] log_id={log_id} synced ticket_id={ticket.id} → resolved")
        else:
            print(f"[APPROVE] log_id={log_id} ticket_id={log.ticket_id} not found in DB")
    else:
        print(f"[APPROVE] log_id={log_id} has no ticket_id — cannot sync ticket")

    db.commit()
    return {
        "message":       f"Action {log_id} approved",
        "id":            log_id,
        "ticket_synced": ticket.id if ticket else None,
    }


@app.get("/operator/mode")
def read_operator_mode(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {"mode": get_operator_mode(db)}


@app.post("/operator/mode")
def update_operator_mode(
    req: OperatorModeRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    mode = set_operator_mode(db, req.mode, by=admin.username)
    return {"mode": mode}

# =============================================================================
# 20. ROUTES — SUPPORT
# =============================================================================


@app.post("/support")
def support(
    req: SupportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return run_support(req, user, db)


@app.post("/support/stream")
async def support_stream(
    req: SupportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = await run_in_threadpool(run_support, req, user, db)
    return StreamingResponse(
        stream_support_events(result),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# =============================================================================
# 21. ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
