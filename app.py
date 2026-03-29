"""
Xalvion Sovereign Brain — app.py
Production-grade FastAPI backend for an AI support/ticketing SaaS.

This version hardens:
- auth validation
- DB/session lifecycle
- streaming thread safety
- refund rule enforcement
- route consistency
- support pipeline resilience
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Generator
from urllib.parse import quote_plus

import stripe
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    func,
    inspect,
    text,
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

SECRET_KEY = os.getenv("JWT_SECRET", "dev_secret_change_me").strip()
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "120"))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_ELITE = os.getenv("STRIPE_PRICE_ELITE", "").strip()

ALLOW_DIRECT_BILLING_BYPASS = (
    os.getenv("ALLOW_DIRECT_BILLING_BYPASS", "false").strip().lower() == "true"
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8001").rstrip("/")
# Public URL of this FastAPI app (OAuth callback must land on the API, not only a static host).
APP_ORIGIN = os.getenv("APP_ORIGIN", "").strip().rstrip("/") or FRONTEND_URL
CHECKOUT_SUCCESS_URL = os.getenv("CHECKOUT_SUCCESS_URL", f"{FRONTEND_URL}?checkout=success")
CHECKOUT_CANCEL_URL = os.getenv("CHECKOUT_CANCEL_URL", f"{FRONTEND_URL}?checkout=cancel")
STRIPE_CONNECT_CLIENT_ID = os.getenv("STRIPE_CONNECT_CLIENT_ID", "").strip()
STRIPE_CONNECT_REDIRECT_URI = os.getenv(
    "STRIPE_CONNECT_REDIRECT_URI",
    f"{APP_ORIGIN}/integrations/stripe/callback",
).strip()

STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", "18"))
STREAM_CHUNK_DELAY = float(os.getenv("STREAM_CHUNK_DELAY", "0.02"))
STATUS_STEP_DELAY = float(os.getenv("STATUS_STEP_DELAY", "0.22"))
MAX_AUTO_REFUND = float(os.getenv("MAX_AUTO_REFUND", "50"))

APPROVAL_THRESHOLD = float(os.getenv("APPROVAL_THRESHOLD", "25.00"))
LIVE_MODE = os.getenv("LIVE_MODE", "false").strip().lower() == "true"
DEBUG_ROUTES_ENABLED = os.getenv("DEBUG_ROUTES_ENABLED", "false").strip().lower() == "true"

REFUND_RULES: dict[str, Any] = {
    "enabled": True,
    "allowed_tiers": {"pro", "elite"},
    "max_auto_refund_amount": 50.00,
    "allowed_issue_types": {
        "duplicate_charge",
        "double_charge",
        "billing_issue",
        "payment_issue",
        "refund_request",
        "billing_duplicate_charge",
        "general_support",
    },
    "blocked_order_statuses": set(),
    "min_confidence": 0.50,
    "min_quality": 0.50,
}

PLAN_CONFIG: dict[str, dict[str, Any]] = {
    "free": {
        "monthly_limit": 50,
        "history_limit": 20,
        "streaming": True,
        "dashboard_access": "basic",
        "priority_routing": False,
        "team_seats": 1,
        "label": "Free",
    },
    "pro": {
        "monthly_limit": 500,
        "history_limit": 500,
        "streaming": True,
        "dashboard_access": "full",
        "priority_routing": True,
        "team_seats": 3,
        "label": "Pro",
    },
    "elite": {
        "monthly_limit": 5000,
        "history_limit": 5000,
        "streaming": True,
        "dashboard_access": "advanced",
        "priority_routing": True,
        "team_seats": 20,
        "label": "Elite",
    },
    "dev": {
        "monthly_limit": 10**9,
        "history_limit": 10**9,
        "streaming": True,
        "dashboard_access": "advanced",
        "priority_routing": True,
        "team_seats": 999,
        "label": "Dev",
    },
}

PUBLIC_PLAN_TIERS = {"free", "pro", "elite"}
PRICE_MAP = {"pro": STRIPE_PRICE_PRO, "elite": STRIPE_PRICE_ELITE}

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
APP_JS_PATH = os.path.join(BASE_DIR, "app.js")
LANDING_PATH = os.path.join(BASE_DIR, "landing.html")
FLUID_DIR = os.path.join(BASE_DIR, "fluid")

# =============================================================================
# FastAPI App + CORS
# =============================================================================

app = FastAPI(title="Xalvion Sovereign Brain")

if os.path.isdir(FLUID_DIR):
    app.mount("/fluid", StaticFiles(directory=FLUID_DIR), name="fluid")

_ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "https://www.xalvion.tech",
    "https://xalvion.tech",
]

for origin in [FRONTEND_URL, APP_ORIGIN] + [
    x.strip().rstrip("/")
    for x in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if x.strip()
]:
    if origin and origin not in _ALLOWED_ORIGINS:
        _ALLOWED_ORIGINS.append(origin)

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
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_rate_log: dict[str, list[float]] = {}
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# 3. MODELS
# =============================================================================


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    usage = Column(Integer, default=0, nullable=False)
    tier = Column(String, default="free", nullable=False)
    stripe_connected = Column(Integer, default=0, nullable=False)
    stripe_account_id = Column(String, nullable=True)
    stripe_livemode = Column(Integer, default=0, nullable=False)
    stripe_scope = Column(String, nullable=True)


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


Base.metadata.create_all(bind=engine)


def ensure_user_columns() -> None:
    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("users")}
        additions = []
        if "stripe_connected" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_connected INTEGER DEFAULT 0 NOT NULL")
        if "stripe_account_id" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_account_id VARCHAR")
        if "stripe_livemode" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_livemode INTEGER DEFAULT 0 NOT NULL")
        if "stripe_scope" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_scope VARCHAR")
        if additions:
            with engine.begin() as conn:
                for statement in additions:
                    conn.execute(text(statement))
    except Exception:
        pass


ensure_user_columns()

# =============================================================================
# 4. ENUM CONSTANTS & VALIDATORS
# =============================================================================

VALID_QUEUES = {"new", "waiting", "escalated", "refund_risk", "vip", "resolved"}
VALID_STATUSES = {"new", "waiting", "escalated", "resolved", "failed"}
VALID_PRIORITIES = {"low", "medium", "high"}
VALID_RISKS = {"low", "medium", "high"}
VALID_OP_MODES = {"conservative", "balanced", "delight", "fraud_aware"}
VALID_CHANNELS = {"web", "email", "api", "chat", "mobile"}
VALID_SOURCES = {"workspace", "sdk", "api", "webhook", "import"}


def _safe_queue(value: Any, default: str = "new") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_QUEUES else default


def _safe_status(value: Any, default: str = "new") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_STATUSES else default


def _safe_priority(value: Any, default: str = "medium") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_PRIORITIES else default


def _safe_risk(value: Any, default: str = "medium") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_RISKS else default


def _safe_op_mode(value: Any, default: str = "balanced") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_OP_MODES else default


def _safe_channel(value: Any, default: str = "web") -> str:
    v = str(value or default).strip().lower()
    return v if v in VALID_CHANNELS else default


def _safe_source(value: Any, default: str = "workspace") -> str:
    v = str(value or default).strip().lower()
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
    message: str
    sentiment: int | None = None
    ltv: int | None = None
    order_status: str | None = None
    payment_intent_id: str | None = None
    charge_id: str | None = None
    refund_reason: str | None = None
    channel: str | None = None
    source: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("message required")
        if len(text) > 10000:
            raise ValueError("message too long")
        return text


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
    status: str | None = None
    queue: str | None = None
    priority: str | None = None
    internal_note: str | None = None


class RefundActionRequest(BaseModel):
    payment_intent_id: str | None = None
    charge_id: str | None = None
    amount: float | None = None
    refund_reason: str | None = None


class ChargeActionRequest(BaseModel):
    customer_id: str
    payment_method_id: str
    amount: int
    currency: str = "usd"
    description: str | None = None

# =============================================================================
# 6. AUTH HELPERS
# =============================================================================


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_username(value: str) -> str:
    return (value or "").strip()


def validate_username(value: str) -> str:
    username = _normalize_username(value)
    if not _USERNAME_RE.fullmatch(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-64 chars and use only letters, numbers, dot, underscore, or dash",
        )
    return username


def validate_password(value: str) -> str:
    password = (value or "").strip()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="Password too long")
    return password


def _bcrypt_safe_password(password: str) -> str:
    raw = (password or "").encode("utf-8")
    if len(raw) > 72:
        return raw[:72].decode("utf-8", errors="ignore")
    return password


def hash_password(password: str) -> str:
    return pwd_context.hash(_bcrypt_safe_password(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_bcrypt_safe_password(plain), hashed)


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_stripe_state(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=15)
    payload = {
        "sub": username,
        "exp": int(expire.timestamp()),
        "purpose": "stripe_connect",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_stripe_state(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "stripe_connect":
            return None
        sub = payload.get("sub")
        return sub if isinstance(sub, str) and sub.strip() else None
    except JWTError:
        return None


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return sub if isinstance(sub, str) and sub.strip() else None
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

    token = authorization.split(" ", 1)[1].strip()
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found — this token no longer matches an account. Log in again.",
        )
    return user


def get_current_username_from_header(authorization: str | None) -> str:
    if not authorization:
        return "guest"
    if not authorization.startswith("Bearer "):
        return "guest"
    token = authorization.split(" ", 1)[1].strip()
    return decode_token(token) or "guest"


def require_authenticated_user(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "username", "") in {"", "guest"}:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not ADMIN_USERNAME or user.username != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def check_rate_limit(user_id: str) -> bool:
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
    plan = get_plan_config(plan_name)
    usage = int(getattr(user, "usage", 0) or 0)
    limit = int(plan["monthly_limit"])
    remaining = max(0, limit - usage) if limit < 10**9 else limit
    return {
        "tier": plan_name,
        "label": plan["label"],
        "usage": usage,
        "limit": limit,
        "remaining": remaining,
        "dashboard_access": plan["dashboard_access"],
        "priority_routing": plan["priority_routing"],
    }


def build_upgrade_payload(current_tier: str) -> dict[str, Any]:
    current_key = current_tier if current_tier in PUBLIC_PLAN_TIERS else "free"
    suggestions = ["pro", "elite"] if current_key == "free" else ["elite"] if current_key == "pro" else []
    return {
        "current_tier": current_key,
        "available_upgrades": suggestions,
        "plans": {
            tier: {
                "label": cfg["label"],
                "monthly_limit": cfg["monthly_limit"],
                "history_limit": cfg["history_limit"],
                "dashboard_access": cfg["dashboard_access"],
                "priority_routing": cfg["priority_routing"],
                "team_seats": cfg["team_seats"],
                "checkout_ready": bool(PRICE_MAP.get(tier)),
            }
            for tier, cfg in PLAN_CONFIG.items()
            if tier in PUBLIC_PLAN_TIERS
        },
    }


def enforce_plan_limits(user: User) -> None:
    plan_name = get_plan_name(user)
    plan = get_plan_config(plan_name)

    if not check_rate_limit(user.username):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    usage = int(getattr(user, "usage", 0) or 0)
    limit = int(plan["monthly_limit"])
    if usage >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"{plan['label']} plan limit reached. Used {usage}/{limit} tickets. Upgrade to continue.",
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
        raise HTTPException(status_code=400, detail=f"Invalid operator mode. Must be one of: {sorted(VALID_OP_MODES)}")

    state = db.query(OperatorState).order_by(OperatorState.id.asc()).first()
    if not state:
        state = OperatorState(mode=normalized, updated_at=_now_iso(), updated_by=by)
        db.add(state)
    else:
        state.mode = normalized
        state.updated_at = _now_iso()
        state.updated_by = by

    db.commit()
    return normalized


def build_agent_meta(req: SupportRequest, user: User, db: Session | None = None) -> dict[str, Any]:
    plan_name = get_plan_name(user)
    operator_mode = get_operator_mode(db) if db is not None else "balanced"
    return {
        "sentiment": req.sentiment if req.sentiment is not None else 5,
        "ltv": req.ltv if req.ltv is not None else 0,
        "order_status": req.order_status if req.order_status is not None else "unknown",
        "plan_tier": plan_name,
        "priority_routing": get_plan_config(plan_name)["priority_routing"],
        "payment_intent_id": (req.payment_intent_id or "").strip(),
        "charge_id": (req.charge_id or "").strip(),
        "operator_mode": operator_mode,
        "channel": _safe_channel(req.channel),
        "source": _safe_source(req.source),
    }


def create_ticket_record(db: Session, user: User, req: SupportRequest) -> Ticket:
    now = _now_iso()
    ticket = Ticket(
        created_at=now,
        updated_at=now,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        channel=_safe_channel(req.channel),
        source=_safe_source(req.source),
        subject=(req.message or "")[:300],
        customer_message=(req.message or "")[:10000],
        status="new",
        queue="new",
        priority="medium",
        risk_level="medium",
        issue_type="general_support",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_from_result(db: Session, ticket: Ticket, result: dict[str, Any]) -> Ticket:
    decision = result.get("decision") or {}
    triage = result.get("triage") or {}
    output = result.get("output") or {}
    action = str(result.get("action", "none") or "none")
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

    ticket.updated_at = _now_iso()
    ticket.status = _safe_status(status)
    ticket.queue = _safe_queue(raw_queue)
    ticket.priority = _safe_priority(decision.get("priority") or (result.get("meta") or {}).get("priority") or "medium")
    ticket.risk_level = _safe_risk(decision.get("risk_level") or "medium")
    ticket.issue_type = str(result.get("issue_type", "general_support") or "general_support")[:64]
    ticket.final_reply = str(result.get("reply", result.get("final", "")) or "")[:8000]
    ticket.internal_note = str(output.get("internal_note") or "")[:2000]
    ticket.action = action
    ticket.amount = float(result.get("amount", 0) or 0)
    ticket.confidence = float(result.get("confidence", 0) or 0)
    ticket.quality = float(result.get("quality", 0) or 0)
    ticket.requires_approval = int(bool(decision.get("requires_approval", False)))
    ticket.approved = 0
    ticket.urgency = _clamp(triage.get("urgency", 0), 0, 99)
    ticket.churn_risk = _clamp(triage.get("churn_risk", 0), 0, 99)
    ticket.refund_likelihood = _clamp(triage.get("refund_likelihood", 0), 0, 99)
    ticket.abuse_likelihood = _clamp(triage.get("abuse_likelihood", 0), 0, 99)
    ticket.complexity = _clamp(triage.get("complexity", 0), 0, 99)

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
    entry = ActionLog(
        timestamp=_now_iso(),
        username=username,
        ticket_id=ticket_id,
        action=action,
        amount=round(float(amount or 0), 2),
        issue_type=issue_type,
        reason=(reason or "")[:500],
        status=status,
        confidence=round(float(confidence or 0), 4),
        quality=round(float(quality or 0), 4),
        message_snippet=(message_snippet or "")[:200],
        requires_approval=int(requires_approval),
        approved=int(approved),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# =============================================================================
# 9. SERIALIZATION HELPERS
# =============================================================================


def serialize_ticket(ticket: Ticket) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "username": ticket.username,
        "channel": ticket.channel,
        "source": ticket.source,
        "status": ticket.status,
        "queue": ticket.queue,
        "priority": ticket.priority,
        "risk_level": ticket.risk_level,
        "issue_type": ticket.issue_type,
        "subject": ticket.subject,
        "customer_message": ticket.customer_message,
        "final_reply": ticket.final_reply,
        "internal_note": ticket.internal_note,
        "action": ticket.action,
        "amount": ticket.amount,
        "confidence": ticket.confidence,
        "quality": ticket.quality,
        "requires_approval": bool(ticket.requires_approval),
        "approved": bool(ticket.approved),
        "urgency": ticket.urgency,
        "churn_risk": ticket.churn_risk,
        "refund_likelihood": ticket.refund_likelihood,
        "abuse_likelihood": ticket.abuse_likelihood,
        "complexity": ticket.complexity,
    }


def serialize_ticket_with_log(ticket: Ticket, db: Session) -> dict[str, Any]:
    base = serialize_ticket(ticket)
    log = (
        db.query(ActionLog)
        .filter(ActionLog.ticket_id == ticket.id)
        .order_by(ActionLog.id.desc())
        .first()
    )
    if log:
        base["action_log"] = {
            "log_id": log.id,
            "action": log.action,
            "amount": log.amount,
            "status": log.status,
            "reason": log.reason,
            "confidence": log.confidence,
            "quality": log.quality,
            "requires_approval": bool(log.requires_approval),
            "approved": bool(log.approved),
            "timestamp": log.timestamp,
        }
    else:
        base["action_log"] = None
    return base


def serialize_support_result(result: dict[str, Any], user: User) -> dict[str, Any]:
    usage_summary = get_usage_summary(user)
    tool_result = result.get("tool_result") or {}
    impact = result.get("impact") or {}

    return {
        "reply": result.get("response", result.get("final", "No response")),
        "mode": result.get("mode", "unknown"),
        "quality": result.get("quality", 0),
        "confidence": result.get("confidence", 0),
        "action": result.get("action", "none"),
        "amount": result.get("amount", 0),
        "reason": result.get("reason", ""),
        "issue_type": result.get("issue_type", "general_support"),
        "order_status": result.get("order_status", "unknown"),
        "tool_result": tool_result,
        "tool_status": result.get("tool_status", tool_result.get("status", "unknown")),
        "impact": impact,
        "decision": result.get("decision", {}),
        "output": result.get("output", {}),
        "meta": result.get("meta", {}),
        "triage": result.get("triage", {}),
        "history": result.get("history", {}),
        "tier": usage_summary["tier"],
        "plan_limit": usage_summary["limit"],
        "usage": usage_summary["usage"],
        "remaining": max(0, get_plan_config(get_public_plan_name(user))["monthly_limit"] - usage_summary["usage"]),
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
        "stripe_account_id": getattr(user, "stripe_account_id", None),
    }

# =============================================================================
# 10. BILLING HELPERS (STRIPE)
# =============================================================================


def safe_refund_reason(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text if text in {"duplicate", "fraudulent", "requested_by_customer"} else "requested_by_customer"


def cents_from_dollars(amount: Any) -> int:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return int(round(min(max(value, 0), MAX_AUTO_REFUND) * 100))


def dollars_from_cents(cents: int) -> float:
    return int(cents) / 100


def rewrite_refund_failure_message(reason: str) -> str:
    text = (reason or "").strip().lower()
    if "stripe account not connected" in text or "connect stripe" in text or "stripe_not_connected" in text:
        return "Refund ready — connect Stripe to execute it from your account."
    return (
        "I've opened this for manual review because I couldn't complete the refund automatically. "
        + reason
    ).strip()


def get_charge_context(
    *,
    payment_intent_id: str | None,
    charge_id: str | None,
    stripe_account_id: str | None = None,
    platform_only: bool = False,
) -> dict[str, Any]:
    pi = (payment_intent_id or "").strip()
    cid = (charge_id or "").strip()

    def _stripe_kwargs(acct: str | None) -> dict[str, Any]:
        return {"stripe_account": acct} if acct else {}

    def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        try:
            value = getattr(obj, key)
            return default if value is None else value
        except Exception:
            pass
        try:
            return obj[key]
        except Exception:
            return default

    def _obj_to_dict(obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "to_dict_recursive"):
            try:
                data = obj.to_dict_recursive()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        try:
            data = dict(obj)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _charge_payload(charge_obj: Any) -> dict[str, Any]:
        charge = _obj_to_dict(charge_obj)
        if not charge:
            return {}
        return {
            "charge_id": str(charge.get("id", "") or ""),
            "charge_amount": int(charge.get("amount", 0) or 0),
            "currency": str(charge.get("currency", "usd") or "usd").upper(),
            "captured": bool(charge.get("captured", True)),
            "refunded": bool(charge.get("refunded", False)),
            "amount_refunded": int(charge.get("amount_refunded", 0) or 0),
            "payment_intent_id": str(charge.get("payment_intent", "") or ""),
        }

    def _find_charge_for_intent(intent_id: str, acct: str | None) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
        kwargs = _stripe_kwargs(acct)
        intent_obj = stripe.PaymentIntent.retrieve(intent_id, expand=["latest_charge"], **kwargs)
        intent_status = str(_obj_get(intent_obj, "status", "") or "")
        intent_amount = int(_obj_get(intent_obj, "amount", 0) or 0)
        intent_currency = str(_obj_get(intent_obj, "currency", "usd") or "usd").upper()

        latest_charge = _obj_get(intent_obj, "latest_charge")
        if latest_charge:
            if isinstance(latest_charge, str):
                latest_charge = stripe.Charge.retrieve(latest_charge, **kwargs)
            charge_info = _charge_payload(latest_charge)
            if charge_info.get("charge_id"):
                if not charge_info.get("payment_intent_id"):
                    charge_info["payment_intent_id"] = intent_id
                return charge_info, acct if acct else None, {
                    "status": intent_status,
                    "amount": intent_amount,
                    "currency": intent_currency,
                }

        listed = stripe.Charge.list(payment_intent=intent_id, limit=10, **kwargs)
        for item in list(getattr(listed, "data", None) or []):
            charge_info = _charge_payload(item)
            if charge_info.get("charge_id"):
                if not charge_info.get("payment_intent_id"):
                    charge_info["payment_intent_id"] = intent_id
                return charge_info, acct if acct else None, {
                    "status": intent_status,
                    "amount": intent_amount,
                    "currency": intent_currency,
                }

        return None, acct if acct else None, {
            "status": intent_status,
            "amount": intent_amount,
            "currency": intent_currency,
        }

    if platform_only:
        accounts_to_try: list[str | None] = [None]
    else:
        accounts_to_try = []
        if stripe_account_id:
            accounts_to_try.append(stripe_account_id)
        accounts_to_try.append(None)

    last_error: Exception | None = None

    if pi:
        for acct in accounts_to_try:
            try:
                charge_info, resolved_account, intent_meta = _find_charge_for_intent(pi, acct)
                if charge_info:
                    return {
                        "payment_intent_id": charge_info.get("payment_intent_id") or pi,
                        "charge_id": charge_info.get("charge_id", ""),
                        "charge_amount": int(charge_info.get("charge_amount", intent_meta.get("amount", 0)) or 0),
                        "currency": str(charge_info.get("currency", intent_meta.get("currency", "USD")) or "USD").upper(),
                        "captured": bool(charge_info.get("captured", True)),
                        "refunded": bool(charge_info.get("refunded", False)),
                        "amount_refunded": int(charge_info.get("amount_refunded", 0) or 0),
                        "status": str(intent_meta.get("status", "") or ""),
                        "resolved_stripe_account_id": resolved_account,
                    }

                if str(intent_meta.get("status", "") or "").lower() == "succeeded":
                    return {
                        "payment_intent_id": pi,
                        "charge_id": "",
                        "charge_amount": int(intent_meta.get("amount", 0) or 0),
                        "currency": str(intent_meta.get("currency", "USD") or "USD").upper(),
                        "captured": True,
                        "refunded": False,
                        "amount_refunded": 0,
                        "status": str(intent_meta.get("status", "") or ""),
                        "resolved_stripe_account_id": resolved_account,
                    }

                raise Exception("No charge found for this payment_intent.")
            except Exception as exc:
                last_error = exc

        raise Exception(str(last_error) if last_error else "Payment intent not found.")

    if cid:
        for acct in accounts_to_try:
            try:
                kwargs = _stripe_kwargs(acct)
                charge_obj = stripe.Charge.retrieve(cid, **kwargs)
                charge_info = _charge_payload(charge_obj)

                return {
                    "payment_intent_id": charge_info.get("payment_intent_id", ""),
                    "charge_id": cid,
                    "charge_amount": int(charge_info.get("charge_amount", 0) or 0),
                    "currency": str(charge_info.get("currency", "USD") or "USD").upper(),
                    "captured": bool(charge_info.get("captured", True)),
                    "refunded": bool(charge_info.get("refunded", False)),
                    "amount_refunded": int(charge_info.get("amount_refunded", 0) or 0),
                    "status": "succeeded" if bool(_obj_get(charge_obj, "paid", False)) else str(_obj_get(charge_obj, "status", "") or ""),
                    "resolved_stripe_account_id": acct if acct else None,
                }
            except Exception as exc:
                last_error = exc

        raise Exception(str(last_error) if last_error else "Charge not found.")

    raise Exception("A payment_intent_id or charge_id is required for an automatic refund.")


def evaluate_refund_rules(
    *,
    result: dict[str, Any],
    user: User,
    charge_context: dict[str, Any],
    requested_cents: int,
    refund_cents: int,
) -> dict[str, Any]:
    tier = get_plan_name(user)
    issue_type = str(result.get("issue_type", "general_support") or "general_support").strip().lower()
    order_status = str(result.get("order_status", "unknown") or "unknown").strip().lower()
    confidence = float(result.get("confidence", 0) or 0)
    quality = float(result.get("quality", 0) or 0)

    checks: list[dict[str, Any]] = []

    def _rule(name: str, passed: bool, detail: str) -> None:
        checks.append({"rule": name, "passed": passed, "detail": detail})

    _rule("enabled", REFUND_RULES["enabled"], "Auto refunds enabled" if REFUND_RULES["enabled"] else "Auto refunds disabled")
    _rule("allowed_tier", tier in REFUND_RULES["allowed_tiers"], f"Tier '{tier}' {'allowed' if tier in REFUND_RULES['allowed_tiers'] else 'not allowed'}")
    _rule("allowed_issue_type", issue_type in REFUND_RULES["allowed_issue_types"], f"Issue type '{issue_type}' {'allowed' if issue_type in REFUND_RULES['allowed_issue_types'] else 'not allowed'}")
    _rule("order_status_ok", order_status not in REFUND_RULES["blocked_order_statuses"], f"Order status '{order_status}' acceptable")
    _rule("min_confidence", confidence >= REFUND_RULES["min_confidence"], f"Confidence {confidence:.2f} >= {REFUND_RULES['min_confidence']:.2f}")
    _rule("min_quality", quality >= REFUND_RULES["min_quality"], f"Quality {quality:.2f} >= {REFUND_RULES['min_quality']:.2f}")

    charge_amount = int(charge_context["charge_amount"])
    amount_refunded = int(charge_context.get("amount_refunded", 0) or 0)
    remaining = max(0, charge_amount - amount_refunded)

    _rule("captured", bool(charge_context.get("captured", False)), "Charge is captured")
    _rule("has_refundable", remaining > 0, f"Remaining refundable: ${dollars_from_cents(remaining):.2f}")
    _rule("within_cap", dollars_from_cents(refund_cents) <= REFUND_RULES["max_auto_refund_amount"], f"${dollars_from_cents(refund_cents):.2f} <= cap ${REFUND_RULES['max_auto_refund_amount']:.2f}")
    _rule("positive_request", requested_cents > 0, f"Requested: ${dollars_from_cents(requested_cents):.2f}")
    _rule("positive_refund", refund_cents > 0, f"Actual: ${dollars_from_cents(refund_cents):.2f}")

    blocked = [r for r in checks if not r["passed"]]
    return {
        "allowed": len(blocked) == 0,
        "blocked_rules": blocked,
        "all_rules": checks,
        "tier": tier,
        "issue_type": issue_type,
        "order_status": order_status,
        "confidence": confidence,
        "quality": quality,
        "requested_amount": dollars_from_cents(requested_cents),
        "charge_amount": dollars_from_cents(charge_amount),
        "remaining_refundable_amount": dollars_from_cents(remaining),
        "refund_amount": dollars_from_cents(refund_cents),
    }


def execute_real_refund(
    *,
    amount: float | int,
    payment_intent_id: str | None,
    charge_id: str | None,
    refund_reason: str | None,
    username: str,
    issue_type: str,
    user: User,
    result: dict[str, Any],
) -> dict[str, Any]:
    pi = (payment_intent_id or "").strip()
    cid = (charge_id or "").strip()

    if not STRIPE_KEY:
        return {"ok": False, "status": "stripe_not_configured", "detail": "Stripe not configured."}
    if not pi and not cid:
        return {"ok": False, "status": "missing_payment_reference", "detail": "payment_intent_id or charge_id required."}

    cents_requested = cents_from_dollars(amount)
    full_refund = cents_requested <= 0

    connected_account_id = str(getattr(user, "stripe_account_id", "") or "").strip()
    connected_enabled = bool(getattr(user, "stripe_connected", 0)) and bool(connected_account_id)

    lookup_attempts: list[tuple[str, dict[str, Any] | None]] = []

    try:
        ctx: dict[str, Any] | None = None

        if connected_enabled:
            try:
                ctx = get_charge_context(
                    payment_intent_id=pi,
                    charge_id=cid,
                    stripe_account_id=connected_account_id,
                    platform_only=False,
                )
                lookup_attempts.append(("connected_or_fallback", ctx))
            except Exception as exc:
                lookup_attempts.append(("connected_or_fallback_error", {"detail": str(exc)}))

        if ctx is None:
            try:
                ctx = get_charge_context(
                    payment_intent_id=pi,
                    charge_id=cid,
                    stripe_account_id=None,
                    platform_only=True,
                )
                lookup_attempts.append(("platform_only", ctx))
            except Exception as exc:
                lookup_attempts.append(("platform_only_error", {"detail": str(exc)}))
                raise exc

        payment_status = str(ctx.get("status", "") or "").lower()
        if payment_status and payment_status != "succeeded":
            return {
                "ok": False,
                "status": "payment_not_refundable",
                "detail": f"Cannot refund payment with status: {payment_status}",
                "charge_context": ctx,
                "lookup_attempts": lookup_attempts,
            }

        charge_amount = int(ctx["charge_amount"])
        already_refunded = int(ctx.get("amount_refunded", 0) or 0)
        remaining = max(0, charge_amount - already_refunded)

        if remaining <= 0:
            return {
                "ok": False,
                "status": "no_refundable_balance",
                "detail": "No refundable balance remaining.",
                "charge_context": ctx,
                "lookup_attempts": lookup_attempts,
            }

        if full_refund:
            refund_cents = remaining
            rules_requested_cents = remaining
        else:
            refund_cents = min(cents_requested, remaining)
            rules_requested_cents = cents_requested

        rules_summary = evaluate_refund_rules(
            result=result,
            user=user,
            charge_context=ctx,
            requested_cents=rules_requested_cents,
            refund_cents=refund_cents,
        )

        if not rules_summary["allowed"]:
            blocked_details = "; ".join(r["detail"] for r in rules_summary["blocked_rules"])
            return {
                "ok": False,
                "status": "refund_blocked_by_rules",
                "detail": blocked_details or "Blocked by rules.",
                "rules_summary": rules_summary,
                "charge_context": ctx,
                "lookup_attempts": lookup_attempts,
            }

        meta_requested = str(rules_requested_cents if full_refund else cents_requested)
        refund_data: dict[str, Any] = {
            "reason": safe_refund_reason(refund_reason),
            "metadata": {
                "source": "xalvion",
                "username": username,
                "issue_type": issue_type,
                "requested_refund_cents": meta_requested,
                "charge_amount_cents": str(charge_amount),
                "rule_tier": rules_summary["tier"],
            },
        }

        if pi:
            refund_data["payment_intent"] = pi
        else:
            refund_data["charge"] = cid

        resolved_account = ctx.get("resolved_stripe_account_id")
        if resolved_account:
            refund_data["stripe_account"] = resolved_account

        if not full_refund and refund_cents > 0:
            refund_data["amount"] = refund_cents

        refund = stripe.Refund.create(**refund_data)
        refund_amount = int(getattr(refund, "amount", refund_cents) or refund_cents) / 100

        return {
            "ok": True,
            "status": "refunded",
            "refund_id": getattr(refund, "id", ""),
            "amount": refund_amount,
            "currency": ctx["currency"],
            "payment_intent_id": ctx["payment_intent_id"] or pi,
            "charge_id": ctx["charge_id"] or cid,
            "requested_amount": rules_requested_cents / 100,
            "charge_amount": charge_amount / 100,
            "remaining_refundable_amount": remaining / 100,
            "capped": (not full_refund) and refund_cents < cents_requested,
            "rules_summary": rules_summary,
            "charge_context": ctx,
            "lookup_attempts": lookup_attempts,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "stripe_refund_failed",
            "detail": str(exc),
            "lookup_attempts": lookup_attempts,
        }


def require_connected_stripe_account(user: User) -> str:
    if not STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured.")
    stripe_account_id = str(getattr(user, "stripe_account_id", "") or "").strip()
    if stripe_account_id:
        return stripe_account_id
    raise HTTPException(status_code=400, detail="Missing connected Stripe account.")


def execute_manual_charge(
    *,
    user: User,
    customer_id: str,
    payment_method_id: str,
    amount: int,
    currency: str = "usd",
    description: str | None = None,
) -> dict[str, Any]:
    stripe_account_id = require_connected_stripe_account(user)

    cents = int(amount or 0)
    if cents <= 0:
        raise HTTPException(status_code=400, detail="Charge amount must be greater than zero.")

    try:
        intent = stripe.PaymentIntent.create(
            amount=cents,
            currency=(currency or "usd").strip().lower(),
            customer=(customer_id or "").strip(),
            payment_method=(payment_method_id or "").strip(),
            confirm=True,
            off_session=True,
            description=(description or "Xalvion support charge").strip(),
            stripe_account=stripe_account_id,
        )
        return {
            "ok": True,
            "status": str(getattr(intent, "status", "") or ""),
            "payment_intent_id": str(getattr(intent, "id", "") or ""),
            "amount": int(getattr(intent, "amount", cents) or cents) / 100,
            "currency": str(getattr(intent, "currency", currency) or currency).upper(),
            "customer_id": customer_id,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "stripe_charge_failed",
            "detail": str(exc),
        }


def apply_real_actions(result: dict[str, Any], req: SupportRequest, user: User) -> dict[str, Any]:
    result = dict(result or {})
    if str(result.get("action", "none") or "none").lower() != "refund":
        return result

    refund_result = execute_real_refund(
        amount=int(result.get("amount", 0) or 0),
        payment_intent_id=req.payment_intent_id,
        charge_id=req.charge_id,
        refund_reason=req.refund_reason,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        issue_type=str(result.get("issue_type", "general_support") or "general_support"),
        user=user,
        result=result,
    )

    if refund_result.get("ok"):
        refunded_amount = refund_result.get("amount", result.get("amount", 0))
        requested_amount = refund_result.get("requested_amount", refunded_amount)
        capped = bool(refund_result.get("capped", False))
        result["action"] = "refund"
        result["amount"] = refunded_amount
        result["reason"] = f"Refund capped to ${refunded_amount:.2f}" if capped else "Refund processed via Stripe"
        result["tool_status"] = "refunded"
        result["tool_result"] = refund_result
        result["impact"] = {"type": "refund", "amount": refunded_amount}
        if capped:
            result["response"] = (
                f"I've processed the refund. Requested ${requested_amount:.2f} but refundable was "
                f"${refunded_amount:.2f} — refunded the full available balance."
            )
            result["final"] = result["response"]
        return result

    failure = str(refund_result.get("detail", "Automatic refund failed.")).strip()
    result["action"] = "review"
    result["amount"] = 0
    result["reason"] = failure
    result["tool_status"] = refund_result.get("status", "refund_failed")
    result["tool_result"] = refund_result
    result["impact"] = {"type": "saved", "amount": 0}
    result["response"] = rewrite_refund_failure_message(failure)
    result["final"] = result["response"]
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
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            metadata={"username": user.username, "tier": desired},
            subscription_data={"metadata": {"username": user.username, "tier": desired}},
            client_reference_id=user.username,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stripe checkout error: {exc}") from exc

    return session


def apply_successful_upgrade(db: Session, username: str, tier: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    desired = (tier or "").strip().lower()
    if desired not in {"pro", "elite"}:
        return user

    user.tier = desired
    db.commit()
    db.refresh(user)
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
    except Exception:
        return ""

    return ""

# =============================================================================
# 11. SUPPORT PIPELINE
# =============================================================================


def check_requires_approval(action: str, amount: float) -> bool:
    if not LIVE_MODE:
        return False
    return action == "refund" and float(amount or 0) > APPROVAL_THRESHOLD


def run_support(req: SupportRequest, user: User, db: Session) -> dict[str, Any]:
    enforce_plan_limits(user)
    ticket = create_ticket_record(db, user, req)

    try:
        result = run_agent(
            req.message,
            user_id=user.username,
            meta=build_agent_meta(req, user, db),
        )

        if not isinstance(result, dict):
            raise RuntimeError("Agent returned invalid payload")

        action = str(result.get("action", "none") or "none").lower()
        amount = float(result.get("amount", 0) or 0)

        needs_approval = (
            check_requires_approval(action, amount)
            or bool((result.get("decision") or {}).get("requires_approval", False))
        )

        if needs_approval:
            result["action"] = "review"
            result["amount"] = 0
            result["reason"] = (
                f"Refund ${amount:.2f} exceeds approval threshold ${APPROVAL_THRESHOLD:.2f}. "
                "Manual approval required."
            )
            result["response"] = (
                "I've flagged this refund for manual approval. Your team will review and process it shortly."
            )
            result["final"] = result["response"]
            result["reply"] = result["response"]
            result["tool_status"] = "pending_approval"
            result.setdefault("decision", {}).update({
                "requires_approval": True,
                "queue": "refund_risk",
                "priority": "high",
                "risk_level": "high",
            })
        else:
            result = apply_real_actions(result, req, user)

        update_ticket_from_result(db, ticket, result)

        log_action(
            db,
            username=str(getattr(user, "username", "unknown")),
            ticket_id=ticket.id,
            action=str(result.get("action", "none")),
            amount=float(result.get("amount", 0) or 0),
            issue_type=str(result.get("issue_type", "general_support")),
            reason=str(result.get("reason", "")),
            status=str(result.get("tool_status", "executed")),
            confidence=float(result.get("confidence", 0) or 0),
            quality=float(result.get("quality", 0) or 0),
            message_snippet=(req.message or "")[:200],
            requires_approval=needs_approval,
            approved=False,
        )

        if hasattr(user, "usage") and getattr(user, "username", "") not in {"dev_user", "guest"}:
            user.usage = int(getattr(user, "usage", 0) or 0) + 1
            db.commit()
            db.refresh(user)

        serialized = serialize_support_result(result, user)
        serialized["ticket"] = serialize_ticket(ticket)
        serialized["operator_mode"] = get_operator_mode(db)
        return serialized

    except HTTPException:
        raise

    except Exception as exc:
        try:
            ticket.status = "failed"
            ticket.queue = "escalated"
            ticket.internal_note = f"Pipeline error: {str(exc)[:500]}"
            ticket.updated_at = _now_iso()
            db.commit()
        except Exception:
            pass

        fallback = (
            "I encountered an issue processing your request. "
            "Our team has been notified and will follow up shortly."
        )
        plan = get_plan_name(user)
        return {
            "reply": fallback,
            "final": fallback,
            "response": fallback,
            "action": "review",
            "amount": 0,
            "reason": "Pipeline error — escalated for manual review",
            "issue_type": "general_support",
            "order_status": "unknown",
            "tool_status": "error",
            "tool_result": {"status": "error"},
            "impact": {"type": "saved", "amount": 0},
            "decision": {"action": "review", "queue": "escalated", "priority": "high"},
            "output": {"internal_note": f"Error: {str(exc)[:200]}"},
            "meta": {},
            "triage": {},
            "history": {},
            "mode": "error",
            "confidence": 0.0,
            "quality": 0.0,
            "tier": plan,
            "plan_limit": get_plan_config(plan)["monthly_limit"],
            "usage": int(getattr(user, "usage", 0) or 0),
            "remaining": max(0, get_plan_config(plan)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
            "ticket": serialize_ticket(ticket),
            "operator_mode": "balanced",
        }


def run_support_for_username(req: SupportRequest, username: str) -> dict[str, Any]:
    with db_session() as db:
        if username and username != "guest":
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username="guest", password="", usage=0, tier="free")
        else:
            user = User(username="guest", password="", usage=0, tier="free")
        return run_support(req, user, db)

# =============================================================================
# 12. STREAMING HELPERS
# =============================================================================


def sse_event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chunk_text(text: str, size: int = STREAM_CHUNK_SIZE) -> list[str]:
    text = text or ""
    if not text:
        return [""]
    return [text[i:i + size] for i in range(0, len(text), size)]


def build_status_sequence(result: dict[str, Any]) -> list[dict[str, str]]:
    seq = [
        {"stage": "reviewing", "label": "Reviewing request"},
        {"stage": "routing", "label": "Choosing next step"},
    ]
    action = str(result.get("action", "none") or "none")
    label = {
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
        yield sse_event("done", {"ok": True})

    return generator()

# =============================================================================
# 13. ROUTES — STATIC
# =============================================================================


@app.get("/")
def serve_index():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return JSONResponse({"status": "ok", "service": "xalvion-sovereign-brain", "warning": "index.html not found"})


@app.get("/debug/refund-mode")
def debug_refund_mode(user: User = Depends(require_admin)):
    if not DEBUG_ROUTES_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "mode": "platform-fallback-v2-latest-charge",
        "has_stripe_key": bool(STRIPE_KEY),
    }


@app.get("/debug/payment-intent/{payment_intent_id}")
def debug_payment_intent(
    payment_intent_id: str,
    user: User = Depends(require_admin),
):
    if not DEBUG_ROUTES_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            expand=["latest_charge", "charges"],
        )

        def _as_dict(obj):
            if obj is None:
                return None
            if hasattr(obj, "to_dict_recursive"):
                return obj.to_dict_recursive()
            if isinstance(obj, dict):
                return obj
            try:
                return dict(obj)
            except Exception:
                return str(obj)

        intent_dict = _as_dict(intent) or {}
        latest_charge = intent_dict.get("latest_charge")
        charges = ((intent_dict.get("charges") or {}).get("data") or [])

        return {
            "id": intent_dict.get("id"),
            "status": intent_dict.get("status"),
            "amount": intent_dict.get("amount"),
            "currency": intent_dict.get("currency"),
            "latest_charge_type": type(latest_charge).__name__,
            "latest_charge": latest_charge,
            "charges_count": len(charges),
            "charges": charges,
        }
    except Exception as exc:
        return {"error": str(exc)}

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
    from sqlalchemy import text as _text

    checks: dict[str, Any] = {}

    try:
        db.execute(_text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        checks["users"] = db.query(User).count()
        checks["tickets"] = db.query(Ticket).count()
        checks["actions"] = db.query(ActionLog).count()
    except Exception as exc:
        checks["tables"] = f"error: {exc}"

    try:
        checks["operator_mode"] = get_operator_mode(db)
    except Exception as exc:
        checks["operator_mode"] = f"error: {exc}"

    degraded = any(isinstance(v, str) and v.startswith("error") for v in checks.values())
    checks["status"] = "degraded" if degraded else "ok"
    checks["service"] = "xalvion-sovereign-brain"
    return checks

# =============================================================================
# 15. ROUTES — AUTH
# =============================================================================


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    usage_summary = get_usage_summary(user)
    public_username = "" if user.username in {"guest", "dev_user"} else user.username
    public_tier = get_public_plan_name(user)
    public_plan = get_plan_config(public_tier)
    public_limit = int(public_plan["monthly_limit"])
    return {
        "username": public_username,
        "tier": public_tier,
        "usage": usage_summary["usage"],
        "limit": public_limit,
        "remaining": max(0, public_limit - usage_summary["usage"]),
        "dashboard_access": public_plan["dashboard_access"],
        "priority_routing": public_plan["priority_routing"],
        "is_dev": usage_summary["tier"] == "dev" and user.username == ADMIN_USERNAME,
        "is_admin": user.username == ADMIN_USERNAME,
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
        "stripe_account_id": getattr(user, "stripe_account_id", None),
    }


@app.post("/signup")
def signup(req: AuthRequest, db: Session = Depends(get_db)):
    username = validate_username(req.username)
    password = validate_password(req.password)

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    db.add(User(username=username, password=hash_password(password), usage=0, tier="free"))
    db.commit()
    return {"message": "Account created", "tier": "free"}


@app.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    username = _normalize_username(req.username)
    password = (req.password or "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.username == ADMIN_USERNAME and user.tier != "elite":
        user.tier = "elite"
        db.commit()
        db.refresh(user)

    token = create_token(user.username)
    usage_summary = get_usage_summary(user)
    return {
        "token": token,
        "username": user.username,
        "tier": usage_summary["tier"],
        "usage": usage_summary["usage"],
        "limit": usage_summary["limit"],
        "remaining": usage_summary["remaining"],
        "is_admin": user.username == ADMIN_USERNAME,
    }



@app.get("/integrations/status")
def integration_status(
    user: User = Depends(require_authenticated_user),
):
    connected = bool(getattr(user, "stripe_connected", 0))
    livemode = bool(getattr(user, "stripe_livemode", 0))
    scope = str(getattr(user, "stripe_scope", "") or "").strip()

    mode_label = ""
    if connected:
        mode_label = "Live" if livemode else "Test"
        if scope:
            mode_label = f"{mode_label} · {scope}"

    return {
        "stripe_connected": connected,
        "stripe_account_id": getattr(user, "stripe_account_id", None),
        "stripe_livemode": livemode,
        "stripe_scope": scope,
        "mode": mode_label,
        "stripe_mode": mode_label,
    }


@app.get("/integrations/stripe/connect")
def integrations_stripe_connect(user: User = Depends(require_authenticated_user)):
    if not STRIPE_KEY or not STRIPE_CONNECT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Stripe Connect is not configured.")

    state = create_stripe_state(user.username)
    url = (
        "https://connect.stripe.com/oauth/authorize"
        f"?response_type=code"
        f"&client_id={STRIPE_CONNECT_CLIENT_ID}"
        f"&scope=read_write"
        f"&state={state}"
        f"&redirect_uri={STRIPE_CONNECT_REDIRECT_URI}"
    )
    return {"url": url}


@app.get("/integrations/stripe/callback")
def stripe_connect_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        detail = error_description or error or "Stripe connection was not completed."
        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=error&detail={quote_plus(detail)}",
            status_code=303,
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=error&detail={quote_plus('Missing Stripe callback parameters.')}",
            status_code=303,
        )

    username = decode_stripe_state(state)
    if not username:
        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=error&detail={quote_plus('Invalid or expired Stripe connect state.')}",
            status_code=303,
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=error&detail={quote_plus('No account matches this Stripe session. Log in again and reconnect.')}",
            status_code=303,
        )

    try:
        token_response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=code,
        )

        user.stripe_connected = 1
        user.stripe_account_id = token_response["stripe_user_id"]
        user.stripe_livemode = 1 if bool(token_response["livemode"]) else 0
        user.stripe_scope = str(token_response["scope"]) if token_response["scope"] else ""

        db.commit()

        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=success&detail={quote_plus('Stripe connected successfully.')}",
            status_code=303,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{FRONTEND_URL}?stripe=error&detail={quote_plus(str(exc))}",
            status_code=303,
        )


@app.post("/integrations/stripe/disconnect")
def integrations_stripe_disconnect(user: User = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.stripe_connected = 0
    db_user.stripe_account_id = None
    db_user.stripe_livemode = 0
    db_user.stripe_scope = None
    db.commit()
    return {"ok": True, "stripe_connected": False}


@app.post("/actions/refund")
def actions_refund(
    req: RefundActionRequest,
    user: User = Depends(require_authenticated_user),
):
    result = execute_real_refund(
        amount=float(req.amount or 0),
        payment_intent_id=req.payment_intent_id,
        charge_id=req.charge_id,
        refund_reason=req.refund_reason,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        issue_type="manual_refund",
        user=user,
        result={
            "action": "refund",
            "amount": float(req.amount or 0),
            "issue_type": "manual_refund",
            "order_status": "unknown",
            "confidence": 0.99,
            "quality": 0.99,
        },
    )

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("detail", "Refund failed.")))

    return result


@app.post("/actions/charge")
def actions_charge(
    req: ChargeActionRequest,
    user: User = Depends(require_authenticated_user),
):
    result = execute_manual_charge(
        user=user,
        customer_id=req.customer_id,
        payment_method_id=req.payment_method_id,
        amount=req.amount,
        currency=req.currency,
        description=req.description,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("detail", "Charge failed.")))

    return result

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
    desired = (req.tier or "").strip().lower()
    current_tier = get_public_plan_name(user)
    validate_upgrade_request(desired, current_tier)

    if STRIPE_KEY and PRICE_MAP.get(desired):
        session = create_checkout_session_for_user(user, desired)
        return {
            "mode": "checkout",
            "checkout_url": session.url,
            "session_id": session.id,
            "tier": current_tier,
            "usage": int(getattr(user, "usage", 0) or 0),
            "limit": get_plan_config(current_tier)["monthly_limit"],
            "remaining": max(0, get_plan_config(current_tier)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
        }

    if not ALLOW_DIRECT_BILLING_BYPASS:
        raise HTTPException(
            status_code=500,
            detail=(
                "Stripe not fully configured. Set STRIPE_SECRET_KEY and price IDs, "
                "or enable ALLOW_DIRECT_BILLING_BYPASS for local testing."
            ),
        )

    user.tier = desired
    db.commit()
    db.refresh(user)
    usage_summary = get_usage_summary(user)
    return {
        "mode": "direct",
        "message": f"Upgraded to {desired}",
        "tier": usage_summary["tier"],
        "usage": usage_summary["usage"],
        "limit": usage_summary["limit"],
        "remaining": usage_summary["remaining"],
    }


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = (
            stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
            if STRIPE_WEBHOOK_SECRET
            else stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook parse failed: {exc}") from exc

    event_type = str(getattr(event, "type", "") or "")
    event_data = getattr(event, "data", None)
    data_object = getattr(event_data, "object", None)
    event_id = str(getattr(event, "id", "") or "")

    if event_id:
        existing = db.query(ProcessedWebhook).filter(ProcessedWebhook.event_id == event_id).first()
        if existing:
            return {"received": True, "type": event_type, "duplicate": True}

        try:
            db.add(ProcessedWebhook(
                event_id=event_id,
                event_type=event_type,
                processed_at=_now_iso(),
                outcome="processing",
            ))
            db.commit()
        except Exception:
            db.rollback()
            return {"received": True, "type": event_type, "duplicate": True}

    outcome = "ok"
    detail = ""

    try:
        if event_type == "checkout.session.completed":
            metadata = getattr(data_object, "metadata", None) or {}
            if not isinstance(metadata, dict):
                try:
                    metadata = dict(metadata)
                except Exception:
                    metadata = {}

            client_reference_id = getattr(data_object, "client_reference_id", None) or ""
            session_id = getattr(data_object, "id", None)
            username = (metadata.get("username") or client_reference_id or "").strip()
            tier = (metadata.get("tier") or "").strip().lower()

            if not tier and session_id:
                tier = infer_tier_from_checkout_session(session_id)

            if username and tier:
                upgraded_user = apply_successful_upgrade(db, username, tier)
                if not upgraded_user:
                    outcome = "skipped"
                    detail = f"User not found: {username!r}"
            else:
                outcome = "skipped"
                detail = "Missing username or tier in event payload"

        elif event_type in {"customer.subscription.deleted", "customer.subscription.updated"}:
            pass

    except Exception as process_exc:
        outcome = "failed"
        detail = str(process_exc)[:500]

    if event_id:
        try:
            record = db.query(ProcessedWebhook).filter(ProcessedWebhook.event_id == event_id).first()
            if record:
                record.outcome = outcome
                record.detail = detail
                db.commit()
        except Exception:
            pass

    return {"received": True, "type": event_type, "outcome": outcome}

# =============================================================================
# 17. ROUTES — DASHBOARD & METRICS
# =============================================================================


@app.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_metrics = get_metrics() or {}

    total_tickets = db.query(Ticket).count()
    auto_resolved = db.query(Ticket).filter(Ticket.status == "resolved").count()
    escalated = db.query(Ticket).filter(Ticket.status.in_(["waiting", "escalated"])).count()
    failed_count = db.query(Ticket).filter(Ticket.status == "failed").count()
    high_risk = db.query(Ticket).filter(Ticket.churn_risk >= 60).count()
    pending_approvals = db.query(ActionLog).filter(
        ActionLog.requires_approval == 1,
        ActionLog.approved == 0,
    ).count()

    refund_total = float(db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "refund").scalar() or 0)
    credit_total = float(db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "credit").scalar() or 0)
    actions_done = db.query(ActionLog).filter(ActionLog.action.in_(["refund", "credit"])).count()
    approved_count = db.query(ActionLog).filter(ActionLog.approved == 1).count()

    db_avg_conf = float(db.query(func.avg(ActionLog.confidence)).filter(ActionLog.confidence > 0).scalar() or 0)
    db_avg_qual = float(db.query(func.avg(ActionLog.quality)).filter(ActionLog.quality > 0).scalar() or 0)
    avg_confidence = file_metrics.get("avg_confidence") or round(db_avg_conf, 4)
    avg_quality = file_metrics.get("avg_quality") or round(db_avg_qual, 4)

    queue_rows = db.query(Ticket.queue, func.count(Ticket.id)).group_by(Ticket.queue).all()
    prio_rows = db.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    risk_rows = db.query(Ticket.risk_level, func.count(Ticket.id)).group_by(Ticket.risk_level).all()
    status_rows = db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()

    by_queue = {_safe_queue(q or "new"): int(c) for q, c in queue_rows}
    by_priority = {_safe_priority(p or "medium"): int(c) for p, c in prio_rows}
    by_risk = {_safe_risk(r or "medium"): int(c) for r, c in risk_rows}
    by_status = {_safe_status(s or "new"): int(c) for s, c in status_rows}

    usage_summary = get_usage_summary(user)
    public_tier = get_public_plan_name(user)

    return {
        "total_interactions": file_metrics.get("total_interactions", 0),
        "avg_confidence": avg_confidence,
        "avg_quality": avg_quality,
        "total_tickets": total_tickets,
        "auto_resolved": auto_resolved,
        "escalated": escalated,
        "failed": failed_count,
        "high_churn_risk": high_risk,
        "pending_approvals": pending_approvals,
        "approved_actions": approved_count,
        "auto_resolution_rate": round(auto_resolved / max(1, total_tickets) * 100, 2),
        "escalation_rate": round(escalated / max(1, total_tickets) * 100, 2),
        "refund_total": round(refund_total, 2),
        "credit_total": round(credit_total, 2),
        "money_saved": round(refund_total + credit_total, 2),
        "actions": actions_done,
        "by_queue": by_queue,
        "by_priority": by_priority,
        "by_risk": by_risk,
        "by_status": by_status,
        "your_usage": usage_summary["usage"],
        "your_tier": public_tier,
        "your_limit": get_plan_config(public_tier)["monthly_limit"],
        "remaining": usage_summary["remaining"],
        "dashboard_access": get_plan_config(public_tier)["dashboard_access"],
        "priority_routing": get_plan_config(public_tier)["priority_routing"],
        "operator_mode": get_operator_mode(db),
        "total_users": db.query(User).count(),
        "pro_users": db.query(User).filter(User.tier == "pro").count(),
        "elite_users": db.query(User).filter(User.tier == "elite").count(),
    }

# =============================================================================
# 18. ROUTES — TICKETS
# =============================================================================


@app.get("/tickets")
def list_tickets(
    limit: int = 50,
    offset: int = 0,
    page: int | None = None,
    page_size: int | None = None,
    queue: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    risk_level: str | None = None,
    issue_type: str | None = None,
    username: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import case as _case

    if page_size is not None:
        limit = page_size
    if page is not None:
        offset = max(0, (page - 1)) * max(1, limit)

    q = db.query(Ticket)
    is_admin = getattr(user, "username", "") == ADMIN_USERNAME

    if not is_admin:
        q = q.filter(Ticket.username == user.username)
    elif username:
        q = q.filter(Ticket.username == username.strip())

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

    if search and len(search.strip()) >= 2:
        term = f"%{search.strip()}%"
        q = q.filter(
            Ticket.subject.ilike(term)
            | Ticket.customer_message.ilike(term)
            | Ticket.final_reply.ilike(term)
            | Ticket.internal_note.ilike(term)
            | Ticket.issue_type.ilike(term)
        )

    sort_map = {
        "newest": Ticket.id.desc(),
        "oldest": Ticket.id.asc(),
        "urgency": Ticket.urgency.desc(),
        "churn_risk": Ticket.churn_risk.desc(),
        "priority": _case(
            (Ticket.priority == "high", 3),
            (Ticket.priority == "medium", 2),
            (Ticket.priority == "low", 1),
            else_=0,
        ).desc(),
    }
    q = q.order_by(sort_map.get(sort, Ticket.id.desc()))

    total = q.count()
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    rows = q.offset(offset).limit(limit).all()
    curr_page = (offset // limit) + 1 if limit > 0 else 1

    items = [serialize_ticket(r) for r in rows]
    return {
        "operator_mode": get_operator_mode(db),
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": curr_page,
        "page_size": limit,
        "has_more": (offset + limit) < total,
        "items": items,
        "tickets": items,
    }


@app.get("/tickets/queues")
def ticket_queue_counts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        "queues": queue_counts,
        "statuses": status_counts,
        "operator_mode": get_operator_mode(db),
    }


@app.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if req.status:
        ticket.status = _safe_status(req.status, ticket.status)
    if req.queue:
        ticket.queue = _safe_queue(req.queue, ticket.queue)
    if req.priority:
        ticket.priority = _safe_priority(req.priority, ticket.priority)
    if req.internal_note:
        existing = (ticket.internal_note or "").strip()
        addition = (req.internal_note or "").strip()
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
    limit: int = 200,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    total = db.query(User).count()
    users = db.query(User).order_by(User.username.asc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "users": [{"username": u.username, "tier": u.tier, "usage": u.usage} for u in users],
    }


@app.post("/admin/set-tier")
def admin_set_tier(
    req: AdminUserAction,
    tier: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tier = (tier or "").strip().lower()
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
    limit: int = 100,
    offset: int = 0,
    username: str | None = None,
    action: str | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    q = db.query(ActionLog)

    if username:
        q = q.filter(ActionLog.username == username.strip())
    if action:
        q = q.filter(ActionLog.action == action.strip().lower())

    total = q.count()
    logs = q.order_by(ActionLog.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "username": log.username,
                "ticket_id": log.ticket_id,
                "action": log.action,
                "amount": log.amount,
                "issue_type": log.issue_type,
                "reason": log.reason,
                "status": log.status,
                "confidence": log.confidence,
                "quality": log.quality,
                "message_snippet": log.message_snippet,
                "requires_approval": bool(log.requires_approval),
                "approved": bool(log.approved),
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
            "id": log.id,
            "timestamp": log.timestamp,
            "username": log.username,
            "ticket_id": log.ticket_id,
            "action": log.action,
            "amount": log.amount,
            "issue_type": log.issue_type,
            "reason": log.reason,
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
    log = db.query(ActionLog).filter(ActionLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if log.approved:
        raise HTTPException(status_code=400, detail="Already approved")

    log.approved = 1
    log.status = "approved"

    ticket = None
    if log.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == log.ticket_id).first()
        if ticket:
            ticket.approved = 1
            ticket.status = _safe_status("resolved")
            ticket.queue = _safe_queue("resolved")
            ticket.updated_at = _now_iso()
            existing_note = (ticket.internal_note or "").strip()
            approval_note = f"Approved by {admin.username} at {_now_iso()}"
            ticket.internal_note = (existing_note + "\n" + approval_note).strip() if existing_note else approval_note

    db.commit()
    return {
        "message": f"Action {log_id} approved",
        "id": log_id,
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
    authorization: str | None = Header(None),
):
    username = get_current_username_from_header(authorization)
    result = await run_in_threadpool(run_support_for_username, req, username)
    return StreamingResponse(
        stream_support_events(result),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# =============================================================================
# 21. ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)