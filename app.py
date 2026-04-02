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
import uuid
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
from models import CanonicalAgentResponse, ExtensionAnalyzeRequest, AgentRequestContext
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
from actions import build_ticket as build_support_ticket, calculate_impact, system_decision, triage_ticket
from memory import get_user_memory
from utils import normalize_ticket, safe_execute

try:
    from learning import learn_from_ticket
except Exception:
    def learn_from_ticket(ticket: dict[str, Any], decision: dict[str, Any], outcome: dict[str, Any]) -> None:
        return None

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

REFUND_RULES: dict[str, Any] = {
    "enabled": True,
    "allowed_tiers": {"free", "pro", "elite"},
    "max_auto_refund_amount": 50.00,
    "allowed_issue_types": {
        "duplicate_charge",
        "double_charge",
        "billing_issue",
        "payment_issue",
        "refund_request",
        "billing_duplicate_charge",
        "general_support",
        "manual_refund",
    },
    "blocked_order_statuses": set(),
    "min_confidence": 0.50,
    "min_quality": 0.50,
}

PLAN_CONFIG: dict[str, dict[str, Any]] = {
    "free": {
        "monthly_limit": 12,
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
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?xalvion\.tech$|^http://(localhost|127\.0\.0\.1)(:\d+)?$",
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


class ApprovalDecisionRequest(BaseModel):
    payment_intent_id: str | None = None
    charge_id: str | None = None
    refund_reason: str | None = None
    internal_note: str | None = None


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
    bootstrap_ticket = build_support_ticket(
        req.message,
        user_id=str(getattr(user, "username", "unknown") or "unknown"),
        meta={
            "sentiment": req.sentiment if req.sentiment is not None else 5,
            "ltv": req.ltv if req.ltv is not None else 0,
            "order_status": req.order_status if req.order_status is not None else "unknown",
            "plan_tier": get_plan_name(user),
            "operator_mode": "balanced",
            "channel": _safe_channel(req.channel),
            "source": _safe_source(req.source),
            "customer_history": {},
        },
    )
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
        issue_type=str(bootstrap_ticket.get("issue_type", "general_support") or "general_support")[:64],
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
    reply = result.get("reply") or result.get("response") or result.get("final") or "No response"
    execution = result.get("execution") or {
        "action": result.get("action", "none"),
        "amount": result.get("amount", 0),
        "status": result.get("tool_status", tool_result.get("status", "unknown")),
        "auto_resolved": bool(impact.get("auto_resolved", False)),
        "requires_approval": bool((result.get("decision") or {}).get("requires_approval", False)),
    }

    return {
        "reply": reply,
        "response": result.get("response", reply),
        "final": result.get("final", reply),
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
        "action_result": result.get("action_result", {"status": "no_action", "type": "noop"}),
        "impact": impact,
        "execution": execution,
        "decision": result.get("decision", {}),
        "output": result.get("output", {}),
        "meta": result.get("meta", {}),
        "triage": result.get("triage", {}),
        "history": result.get("history", {}),
        "runtime_ticket": result.get("runtime_ticket", {}),
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

        # For PaymentIntent-based refunds, Stripe is the source of truth on remaining balance.
        # Some Stripe Link / Checkout flows can surface incomplete refund balance data on the
        # expanded charge object even when the PaymentIntent is still refundable.
        if pi:
            rules_ctx = dict(ctx)
            if remaining <= 0:
                rules_ctx["amount_refunded"] = 0
                remaining_for_ui = charge_amount
            else:
                remaining_for_ui = remaining

            if full_refund:
                refund_cents = charge_amount
                rules_requested_cents = charge_amount
            else:
                refund_cents = cents_requested
                rules_requested_cents = cents_requested

            rules_summary = evaluate_refund_rules(
                result=result,
                user=user,
                charge_context=rules_ctx,
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
                    "charge_context": rules_ctx,
                    "lookup_attempts": lookup_attempts,
                }

            meta_requested = str(rules_requested_cents)
            refund_data: dict[str, Any] = {
                "payment_intent": pi,
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
                "remaining_refundable_amount": remaining_for_ui / 100,
                "capped": False,
                "rules_summary": rules_summary,
                "charge_context": rules_ctx,
                "lookup_attempts": lookup_attempts,
            }

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

        refund_data["charge"] = cid or str(ctx.get("charge_id", "") or "")

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


def build_runtime_ticket(req: SupportRequest, user: User, db: Session) -> dict[str, Any]:
    meta = build_agent_meta(req, user, db)
    user_memory = get_user_memory(str(getattr(user, "username", "guest") or "guest"))
    meta["customer_history"] = user_memory
    raw_ticket = build_support_ticket(req.message, user_id=str(getattr(user, "username", "guest") or "guest"), meta=meta)
    ticket = normalize_ticket(raw_ticket)
    ticket["customer_history"] = user_memory
    ticket["triage"] = ticket.get("triage") or triage_ticket(ticket, user_memory)
    return ticket


def hydrate_result_with_engine_context(
    result: dict[str, Any],
    *,
    runtime_ticket: dict[str, Any],
    hard_decision: dict[str, Any],
    impact: dict[str, Any],
    user: User,
) -> dict[str, Any]:
    hydrated = dict(result or {})
    existing_decision = dict(hydrated.get("decision") or {})
    existing_meta = dict(hydrated.get("meta") or {})
    existing_output = dict(hydrated.get("output") or {})

    issue_type = str(hydrated.get("issue_type") or runtime_ticket.get("issue_type") or "general_support")
    order_status = str(hydrated.get("order_status") or runtime_ticket.get("order_status") or "unknown")
    triage = hydrated.get("triage") or runtime_ticket.get("triage") or {}
    history = hydrated.get("history") or runtime_ticket.get("customer_history") or {}

    action = str(hydrated.get("action", existing_decision.get("action", "none")) or "none")
    amount = float(hydrated.get("amount", existing_decision.get("amount", 0)) or 0)
    reason = str(hydrated.get("reason") or existing_decision.get("reason") or hard_decision.get("reason") or "")
    queue = str(existing_decision.get("queue") or hard_decision.get("queue") or "new")
    priority = str(existing_decision.get("priority") or hard_decision.get("priority") or "medium")
    risk_level = str(existing_decision.get("risk_level") or hard_decision.get("risk_level") or triage.get("risk_level") or "medium")
    requires_approval = bool(existing_decision.get("requires_approval", hard_decision.get("requires_approval", False)))

    hydrated["issue_type"] = issue_type
    hydrated["order_status"] = order_status
    hydrated["impact"] = impact or hydrated.get("impact") or {}
    hydrated["triage"] = triage
    hydrated["history"] = history
    hydrated["runtime_ticket"] = runtime_ticket
    hydrated["reply"] = hydrated.get("reply") or hydrated.get("response") or hydrated.get("final") or ""
    hydrated["response"] = hydrated.get("response") or hydrated.get("reply") or hydrated.get("final") or ""
    hydrated["final"] = hydrated.get("final") or hydrated.get("reply") or hydrated.get("response") or ""
    hydrated["reason"] = reason
    hydrated["action"] = action
    hydrated["amount"] = round(amount, 2)

    existing_decision.update({
        "action": action,
        "amount": round(amount, 2),
        "reason": reason,
        "queue": queue,
        "priority": priority,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "shadow": hard_decision,
    })
    hydrated["decision"] = existing_decision

    existing_meta.update({
        "priority": existing_meta.get("priority") or priority,
        "operator_mode": runtime_ticket.get("operator_mode", "balanced"),
        "plan_tier": get_plan_name(user),
        "channel": runtime_ticket.get("channel", "web"),
        "source": runtime_ticket.get("source", "workspace"),
    })
    hydrated["meta"] = existing_meta

    execution_status = str(hydrated.get("tool_status") or (hydrated.get("tool_result") or {}).get("status") or "unknown")
    hydrated["execution"] = {
        "action": action,
        "amount": round(amount, 2),
        "status": execution_status,
        "auto_resolved": bool((impact or {}).get("auto_resolved", False)),
        "requires_approval": requires_approval,
    }

    internal_note = str(existing_output.get("internal_note") or "").strip()
    if not internal_note:
        internal_note = f"Decision: {action} | Queue: {queue} | Priority: {priority} | Risk: {risk_level}"
    existing_output["internal_note"] = internal_note
    hydrated["output"] = existing_output
    return hydrated


def apply_learning_feedback(runtime_ticket: dict[str, Any], result: dict[str, Any]) -> None:
    decision = {
        "action": str(result.get("action", "none") or "none"),
        "amount": float(result.get("amount", 0) or 0),
        "reason": str(result.get("reason", "") or ""),
    }
    outcome = dict(result.get("impact") or {})
    if not outcome:
        outcome = calculate_impact(runtime_ticket, decision)
    safe_execute(learn_from_ticket, runtime_ticket, decision, outcome)


def check_requires_approval(action: str, amount: float) -> bool:
    normalized = str(action or "none").strip().lower()
    value = float(amount or 0)

    if normalized in {"refund", "charge"}:
        return True

    if LIVE_MODE and normalized == "credit" and value > APPROVAL_THRESHOLD:
        return True

    return False


def build_approval_hold_message(action: str, amount: float) -> str:
    normalized = str(action or "none").strip().lower()
    value = round(float(amount or 0), 2)

    if normalized == "refund" and value > 0:
        return f"I’ve prepared a refund of ${value:.2f} and held it for approval before anything is executed."
    if normalized == "charge" and value > 0:
        return f"I’ve prepared a charge of ${value:.2f} and held it for approval before anything is executed."
    if normalized == "credit" and value > 0:
        return f"I’ve prepared a ${value:.2f} credit and held it for approval before anything is executed."
    return "I’ve prepared the next action and held it for approval before anything is executed."


def serialize_pending_approval_result(result: dict[str, Any], *, action: str, amount: float) -> dict[str, Any]:
    pending = dict(result or {})
    reason = str(pending.get("reason", "") or "Approval required before execution")
    hold_message = build_approval_hold_message(action, amount)

    pending["action"] = action
    pending["amount"] = round(float(amount or 0), 2)
    pending["reply"] = hold_message
    pending["response"] = hold_message
    pending["final"] = hold_message
    pending["tool_status"] = "pending_approval"
    pending["tool_result"] = {
        "status": "pending_approval",
        "proposed_action": action,
        "proposed_amount": round(float(amount or 0), 2),
    }

    decision = dict(pending.get("decision") or {})
    decision.update({
        "action": action,
        "amount": round(float(amount or 0), 2),
        "reason": reason,
        "requires_approval": True,
        "status": "waiting",
        "queue": decision.get("queue") or ("refund_risk" if action == "refund" else "waiting"),
        "priority": decision.get("priority") or ("high" if action in {"refund", "charge"} else "medium"),
        "risk_level": decision.get("risk_level") or ("high" if action in {"refund", "charge"} else "medium"),
        "proposed_action": action,
        "proposed_amount": round(float(amount or 0), 2),
    })
    pending["decision"] = decision

    execution = dict(pending.get("execution") or {})
    execution.update({
        "action": action,
        "amount": round(float(amount or 0), 2),
        "status": "pending_approval",
        "auto_resolved": False,
        "requires_approval": True,
        "proposed_action": action,
        "proposed_amount": round(float(amount or 0), 2),
    })
    pending["execution"] = execution
    return pending


def build_ticket_response_payload(ticket: Ticket, log: ActionLog | None = None) -> dict[str, Any]:
    action = str(ticket.action or "none")
    amount = round(float(ticket.amount or 0), 2)
    tool_status = str(log.status if log else ticket.status or "unknown")
    confidence = round(float(ticket.confidence or 0), 2)
    quality = round(float(ticket.quality or 0), 2)
    reason = str(log.reason if log else ticket.internal_note or "")
    reply = str(ticket.final_reply or "")

    return {
        "reply": reply,
        "response": reply,
        "final": reply,
        "action": action,
        "amount": amount,
        "reason": reason,
        "issue_type": str(ticket.issue_type or "general_support"),
        "tool_status": tool_status,
        "confidence": confidence,
        "quality": quality,
        "decision": {
            "action": action,
            "amount": amount,
            "queue": str(ticket.queue or "new"),
            "priority": str(ticket.priority or "medium"),
            "risk_level": str(ticket.risk_level or "medium"),
            "requires_approval": bool(ticket.requires_approval),
            "status": str(ticket.status or "new"),
        },
        "output": {
            "internal_note": str(ticket.internal_note or ""),
        },
        "impact": {
            "type": action,
            "amount": amount,
            "money_saved": 0,
            "auto_resolved": str(ticket.status or "").lower() == "resolved" and not bool(ticket.requires_approval),
        },
        "ticket": serialize_ticket_with_log(ticket, db),
    }


def append_ticket_internal_note(ticket: Ticket, note: str) -> None:
    addition = str(note or "").strip()
    if not addition:
        return
    existing = (ticket.internal_note or "").strip()
    ticket.internal_note = (existing + "\n" + addition).strip() if existing else addition


def approve_ticket_action(ticket: Ticket, log: ActionLog, req: ApprovalDecisionRequest, user: User) -> tuple[dict[str, Any], str]:
    proposed_action = str(log.action or ticket.action or "none").strip().lower()
    proposed_amount = round(float(log.amount or ticket.amount or 0), 2)

    payload = {
        "reply": ticket.final_reply or build_approval_hold_message(proposed_action, proposed_amount),
        "response": ticket.final_reply or build_approval_hold_message(proposed_action, proposed_amount),
        "final": ticket.final_reply or build_approval_hold_message(proposed_action, proposed_amount),
        "action": proposed_action,
        "amount": proposed_amount,
        "reason": str(log.reason or ticket.internal_note or "Approved by operator"),
        "issue_type": ticket.issue_type,
        "tool_status": "approved",
        "tool_result": {"status": "approved"},
        "decision": {
            "action": proposed_action,
            "amount": proposed_amount,
            "queue": ticket.queue,
            "priority": ticket.priority,
            "risk_level": ticket.risk_level,
            "requires_approval": False,
            "status": "resolved",
        },
        "output": {
            "internal_note": str(ticket.internal_note or ""),
        },
    }

    if proposed_action == "refund":
        if (req.payment_intent_id or "").strip() or (req.charge_id or "").strip():
            support_req = SupportRequest(
                message=ticket.customer_message or ticket.subject or "Refund approval",
                payment_intent_id=(req.payment_intent_id or None),
                charge_id=(req.charge_id or None),
                refund_reason=(req.refund_reason or None),
                channel=ticket.channel or "web",
                source=ticket.source or "workspace",
            )
            payload = apply_real_actions(payload, support_req, user)
            payload.setdefault("decision", {}).update({
                "action": str(payload.get("action", proposed_action) or proposed_action),
                "amount": round(float(payload.get("amount", proposed_amount) or proposed_amount), 2),
                "queue": "resolved",
                "priority": ticket.priority or "high",
                "risk_level": ticket.risk_level or "medium",
                "requires_approval": False,
                "status": "resolved",
            })
            if payload.get("tool_status") == "refunded":
                payload["reply"] = payload.get("reply") or payload.get("response") or "I’ve approved the refund and it’s now in motion."
                payload["response"] = payload.get("response") or payload.get("reply")
                payload["final"] = payload.get("final") or payload.get("response") or payload.get("reply")
                return payload, "approved"

        hold = (
            "Approval recorded. Connect Stripe or provide a payment reference to execute this refund from the workspace."
        )
        payload["reply"] = hold
        payload["response"] = hold
        payload["final"] = hold
        payload["tool_status"] = "approved_pending_execution"
        payload["tool_result"] = {"status": "approved_pending_execution"}
        payload.setdefault("decision", {}).update({"status": "waiting", "queue": "waiting"})
        return payload, "approved_pending_execution"

    if proposed_action == "credit":
        payload["reply"] = f"I’ve approved the ${proposed_amount:.2f} credit and it’s ready for the next step."
        payload["response"] = payload["reply"]
        payload["final"] = payload["reply"]
        payload["tool_status"] = "approved"
        payload["tool_result"] = {"status": "approved"}
        return payload, "approved"

    if proposed_action == "charge":
        payload["reply"] = f"I’ve approved the ${proposed_amount:.2f} charge and moved it into the execution path."
        payload["response"] = payload["reply"]
        payload["final"] = payload["reply"]
        payload["tool_status"] = "approved_pending_execution"
        payload["tool_result"] = {"status": "approved_pending_execution"}
        payload.setdefault("decision", {}).update({"status": "waiting", "queue": "waiting"})
        return payload, "approved_pending_execution"

    payload["reply"] = "I’ve approved the prepared action and moved it into the next step."
    payload["response"] = payload["reply"]
    payload["final"] = payload["reply"]
    payload["tool_status"] = "approved"
    payload["tool_result"] = {"status": "approved"}
    return payload, "approved"


def run_support(req: SupportRequest, user: User, db: Session) -> dict[str, Any]:
    enforce_plan_limits(user)
    ticket = create_ticket_record(db, user, req)
    runtime_ticket = build_runtime_ticket(req, user, db)
    shadow_decision = safe_execute(system_decision, runtime_ticket)
    if not isinstance(shadow_decision, dict) or "error" in shadow_decision:
        shadow_decision = {
            "action": "none",
            "amount": 0,
            "reason": "Shadow decision fallback",
            "priority": "medium",
            "risk_level": str((runtime_ticket.get("triage") or {}).get("risk_level", "medium") or "medium"),
            "queue": "new",
            "requires_approval": False,
        }

    try:
        result = run_agent(
            req.message,
            user_id=str(getattr(user, "username", "guest") or "guest"),
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
            result = serialize_pending_approval_result(result, action=action, amount=amount)
        else:
            result = apply_real_actions(result, req, user)

        impact = calculate_impact(runtime_ticket, {
            "action": str(result.get("action", "none") or "none"),
            "amount": float(result.get("amount", 0) or 0),
        })
        result = hydrate_result_with_engine_context(
            result,
            runtime_ticket=runtime_ticket,
            hard_decision=shadow_decision,
            impact=impact,
            user=user,
        )
        apply_learning_feedback(runtime_ticket, result)

        update_ticket_from_result(db, ticket, result)

        action_entry = log_action(
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
        serialized["ticket"] = serialize_ticket_with_log(ticket, db)
        serialized["action_log"] = serialized["ticket"].get("action_log") or {
            "log_id": action_entry.id,
            "action": action_entry.action,
            "amount": action_entry.amount,
            "status": action_entry.status,
            "requires_approval": bool(action_entry.requires_approval),
            "approved": bool(action_entry.approved),
            "timestamp": action_entry.timestamp,
        }
        serialized["operator_mode"] = get_operator_mode(db)
        serialized["shadow_decision"] = shadow_decision
        serialized["runtime_ticket"] = runtime_ticket
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
            "issue_type": str(runtime_ticket.get("issue_type", "general_support") or "general_support"),
            "order_status": str(runtime_ticket.get("order_status", "unknown") or "unknown"),
            "tool_status": "error",
            "tool_result": {"status": "error"},
            "impact": {"type": "saved", "amount": 0, "money_saved": 0, "auto_resolved": False},
            "decision": {"action": "review", "queue": "escalated", "priority": "high", "shadow": shadow_decision},
            "output": {"internal_note": f"Error: {str(exc)[:200]}"},
            "meta": {"operator_mode": runtime_ticket.get("operator_mode", "balanced")},
            "triage": runtime_ticket.get("triage", {}),
            "history": runtime_ticket.get("customer_history", {}),
            "execution": {"action": "review", "amount": 0, "status": "error", "auto_resolved": False, "requires_approval": False},
            "mode": "error",
            "confidence": 0.0,
            "quality": 0.0,
            "tier": plan,
            "plan_limit": get_plan_config(plan)["monthly_limit"],
            "usage": int(getattr(user, "usage", 0) or 0),
            "remaining": max(0, get_plan_config(plan)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
            "ticket": serialize_ticket(ticket),
            "operator_mode": runtime_ticket.get("operator_mode", "balanced"),
            "shadow_decision": shadow_decision,
            "runtime_ticket": runtime_ticket,
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
def debug_refund_mode():
    return {
        "mode": "platform-fallback-v2-latest-charge",
        "has_stripe_key": bool(STRIPE_KEY),
    }


@app.get("/debug/payment-intent/{payment_intent_id}")
def debug_payment_intent(payment_intent_id: str):
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


@app.get("/tickets/pending-approvals")
def list_pending_ticket_approvals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    query = db.query(Ticket).filter(Ticket.requires_approval == 1, Ticket.approved == 0)
    if getattr(user, "username", "") != ADMIN_USERNAME:
        query = query.filter(Ticket.username == user.username)

    tickets = query.order_by(Ticket.updated_at.desc()).limit(50).all()
    return [serialize_ticket_with_log(ticket, db) for ticket in tickets]


@app.post("/tickets/{ticket_id}/approve")
def approve_ticket(
    ticket_id: int,
    req: ApprovalDecisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if getattr(user, "username", "") != ADMIN_USERNAME and ticket.username != user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bool(ticket.requires_approval) or bool(ticket.approved):
        raise HTTPException(status_code=400, detail="No pending approval for this ticket")

    log = (
        db.query(ActionLog)
        .filter(ActionLog.ticket_id == ticket.id, ActionLog.requires_approval == 1, ActionLog.approved == 0)
        .order_by(ActionLog.id.desc())
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Pending approval log not found")

    append_ticket_internal_note(ticket, req.internal_note or "")
    payload, log_status = approve_ticket_action(ticket, log, req, user)

    ticket.updated_at = _now_iso()
    ticket.action = str(payload.get("action", ticket.action) or ticket.action)
    ticket.amount = float(payload.get("amount", ticket.amount) or ticket.amount)
    ticket.final_reply = str(payload.get("reply", payload.get("response", ticket.final_reply)) or ticket.final_reply)[:8000]
    ticket.status = _safe_status((payload.get("decision") or {}).get("status", "resolved"), "resolved")
    ticket.queue = _safe_queue((payload.get("decision") or {}).get("queue", "resolved"), "resolved")
    ticket.priority = _safe_priority((payload.get("decision") or {}).get("priority", ticket.priority or "high"), ticket.priority or "high")
    ticket.risk_level = _safe_risk((payload.get("decision") or {}).get("risk_level", ticket.risk_level or "medium"), ticket.risk_level or "medium")
    ticket.requires_approval = 0
    ticket.approved = 1
    append_ticket_internal_note(ticket, f"Approved by {user.username} at {_now_iso()}")

    log.approved = 1
    log.requires_approval = 0
    log.status = log_status
    log.reason = str(payload.get("reason", log.reason) or log.reason)
    db.commit()
    db.refresh(ticket)
    db.refresh(log)

    response = build_ticket_response_payload(ticket, log)
    response["message"] = f"Ticket {ticket.id} approved"
    return response


@app.post("/tickets/{ticket_id}/reject")
def reject_ticket(
    ticket_id: int,
    req: ApprovalDecisionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(user, "username", "") or user.username == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if getattr(user, "username", "") != ADMIN_USERNAME and ticket.username != user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bool(ticket.requires_approval) or bool(ticket.approved):
        raise HTTPException(status_code=400, detail="No pending approval for this ticket")

    log = (
        db.query(ActionLog)
        .filter(ActionLog.ticket_id == ticket.id, ActionLog.requires_approval == 1, ActionLog.approved == 0)
        .order_by(ActionLog.id.desc())
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Pending approval log not found")

    rejection_note = str(req.internal_note or "Rejected by operator before execution.").strip()
    ticket.updated_at = _now_iso()
    ticket.status = _safe_status("escalated")
    ticket.queue = _safe_queue("escalated")
    ticket.requires_approval = 0
    ticket.approved = 0
    ticket.final_reply = "I’ve held this case for manual follow-up instead of executing the prepared action."
    append_ticket_internal_note(ticket, rejection_note)
    append_ticket_internal_note(ticket, f"Rejected by {user.username} at {_now_iso()}")

    log.status = "rejected"
    log.reason = rejection_note[:500]
    log.requires_approval = 0
    log.approved = 0

    db.commit()
    db.refresh(ticket)
    db.refresh(log)

    response = build_ticket_response_payload(ticket, log)
    response["message"] = f"Ticket {ticket.id} rejected"
    return response


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






def _build_extension_meta(
    req: ExtensionAnalyzeRequest,
    operator_mode: str,
    plan_tier: str,
    priority_routing: bool,
) -> dict[str, Any]:
    return {
        "channel": "email",
        "source": "extension",
        "order_status": req.order_status or "unknown",
        "operator_mode": operator_mode,
        "plan_tier": plan_tier,
        "priority_routing": priority_routing,
        "payment_intent_id": (req.payment_intent_id or "").strip(),
        "charge_id": (req.charge_id or "").strip(),
        "sentiment": req.sentiment if req.sentiment is not None else 5,
        "ltv": req.ltv if req.ltv is not None else 0,
    }


def _build_extension_context(req: ExtensionAnalyzeRequest) -> AgentRequestContext:
    return AgentRequestContext(
        surface="chrome_extension",
        page_url=req.page_url,
        host=req.host,
        page_title=req.page_title,
        app_name=req.app_name,
        thread_id=req.thread_id,
        subject=req.subject,
        sender=req.sender,
        dom_excerpt=req.dom_excerpt,
        selected_text=req.selected_text,
    )


def _persist_sovereign_result(
    db: Session,
    username: str,
    raw_text: str,
    result: dict[str, Any],
) -> None:
    now = _now_iso()
    decision = result.get("sovereign_decision") or {}
    triage = result.get("triage_metadata") or {}
    output = result.get("output") or {}
    request_context = result.get("request_context") or {}

    ticket = Ticket(
        created_at=now,
        updated_at=now,
        username=username,
        channel="email",
        source="extension",
        status=_safe_status(decision.get("status", "new")),
        queue=_safe_queue(decision.get("queue", "new")),
        priority=_safe_priority(decision.get("priority", "medium")),
        risk_level=_safe_risk(decision.get("risk_level", "medium")),
        issue_type=str(result.get("issue_type", "general_support") or "general_support")[:64],
        subject=str(request_context.get("subject", "") or "")[:300],
        customer_message=raw_text[:10000],
        final_reply=str(result.get("reply", result.get("final", "")) or "")[:8000],
        internal_note=str(output.get("internal_note", "") or "")[:2000],
        action=str(decision.get("action", "none") or "none"),
        amount=float(decision.get("amount", 0) or 0),
        confidence=float(decision.get("confidence", 0) or 0),
        quality=float(result.get("quality", 0) or 0),
        requires_approval=int(bool(decision.get("requires_approval", False))),
        approved=0,
        churn_risk=_clamp(triage.get("churn_risk", 0), 0, 99),
        refund_likelihood=_clamp(triage.get("refund_likelihood", 0), 0, 99),
        abuse_likelihood=_clamp(triage.get("abuse_likelihood", 0), 0, 99),
        complexity=_clamp(triage.get("complexity", 0), 0, 99),
        urgency=_clamp(triage.get("urgency", 0), 0, 99),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    log = ActionLog(
        timestamp=now,
        username=username,
        ticket_id=ticket.id,
        action=str(decision.get("action", "none") or "none"),
        amount=round(float(decision.get("amount", 0) or 0), 2),
        issue_type=str(result.get("issue_type", "general_support") or "general_support"),
        reason=str(decision.get("reason", "") or "")[:500],
        status=str(decision.get("tool_status", decision.get("status", "executed")) or "executed"),
        confidence=round(float(decision.get("confidence", 0) or 0), 4),
        quality=round(float(result.get("quality", 0) or 0), 4),
        message_snippet=raw_text[:200],
        requires_approval=int(bool(decision.get("requires_approval", False))),
        approved=0,
    )
    db.add(log)
    db.commit()


@app.post("/analyze", response_model=CanonicalAgentResponse)
def analyze_extension_ticket(
    req: ExtensionAnalyzeRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    username = get_current_username_from_header(authorization)
    user = db.query(User).filter(User.username == username).first() if username != "guest" else None

    if user:
        enforce_plan_limits(user)
        plan_tier = get_plan_name(user)
        priority_routing = bool(get_plan_config(plan_tier)["priority_routing"])
        operator_mode = get_operator_mode(db)
    else:
        username = "extension_guest"
        plan_tier = "free"
        priority_routing = False
        operator_mode = get_operator_mode(db)

    result = run_agent(
        message=req.text,
        user_id=username,
        meta=_build_extension_meta(req, operator_mode, plan_tier, priority_routing),
        request_context=_build_extension_context(req).model_dump(),
    )

    try:
        decision = dict(result.get("sovereign_decision") or {})
        action = str(decision.get("action", "none") or "none").strip().lower()
        amount = round(float(decision.get("amount", 0) or 0), 2)
        if check_requires_approval(action, amount):
            hold_message = build_approval_hold_message(action, amount)
            decision.update({
                "requires_approval": True,
                "status": "waiting",
                "queue": decision.get("queue") or ("refund_risk" if action == "refund" else "waiting"),
                "priority": decision.get("priority") or ("high" if action in {"refund", "charge"} else "medium"),
                "risk_level": decision.get("risk_level") or ("high" if action in {"refund", "charge"} else "medium"),
                "tool_status": "pending_approval",
            })
            result["reply"] = hold_message
            result["response"] = hold_message
            result["final"] = hold_message
            result["sovereign_decision"] = decision
        
    except Exception:
        pass

    if user:
        user.usage = int(user.usage or 0) + 1
        db.commit()

    _persist_sovereign_result(db, username, req.text, result)

    payload = CanonicalAgentResponse.model_validate(result).model_dump()
    return JSONResponse(
        content=payload,
        media_type="application/json; charset=utf-8",
    )


# =============================================================================
# 13. OUTREACH CRM HELPERS
# =============================================================================

OUTREACH_QUEUE_PATH = os.path.join(BASE_DIR, "outreach_queue.json")
LEAD_STATUS_ORDER = {"new", "contacted", "replied", "closed"}
LEAD_STAGE_ORDER = {"lead", "contacted", "replied", "demo", "closed"}


class LeadAddRequest(BaseModel):
    username: str
    text: str
    source: str | None = "manual"

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("username required")
        if len(text) > 120:
            raise ValueError("username too long")
        return text

    @field_validator("text")
    @classmethod
    def validate_text_field(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("text required")
        if len(text) > 5000:
            raise ValueError("text too long")
        return text


class LeadStatusRequest(BaseModel):
    status: str | None = None
    stage: str | None = None
    note: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        status = (v or "").strip().lower()
        if status not in LEAD_STATUS_ORDER:
            raise ValueError("status must be one of new/contacted/replied/closed")
        return status

    @field_validator("stage")
    @classmethod
    def validate_stage_field(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stage = (v or "").strip().lower()
        if stage not in LEAD_STAGE_ORDER:
            raise ValueError("stage must be one of lead/contacted/replied/demo/closed")
        return stage


class LeadReminderRequest(BaseModel):
    days: int | None = 1
    note: str | None = None

    @field_validator("days")
    @classmethod
    def validate_days_field(cls, v: int | None) -> int:
        try:
            value = int(v or 1)
        except Exception:
            value = 1
        return max(1, min(14, value))


class LeadConvertRequest(BaseModel):
    value: float | None = 0
    note: str | None = None

    @field_validator("value")
    @classmethod
    def validate_value_field(cls, v: float | None) -> float:
        try:
            value = float(v or 0)
        except Exception:
            value = 0.0
        return max(0.0, min(1000000.0, value))


def _crm_now() -> datetime:
    return datetime.utcnow()


def _crm_now_iso() -> str:
    return _crm_now().isoformat()


def _infer_lead_source(text: str, source: str | None = None) -> str:
    explicit = str(source or "").strip().lower()
    if explicit and explicit not in {"", "manual", "unknown", "n/a"}:
        if explicit == "x":
            return "twitter"
        return explicit
    lowered = str(text or "").lower()
    if "reddit" in lowered or "r/" in lowered or "subreddit" in lowered:
        return "reddit"
    if "twitter" in lowered or "tweet" in lowered or "x.com" in lowered or " on x " in f" {lowered} ":
        return "twitter"
    if "linkedin" in lowered:
        return "linkedin"
    if "shopify" in lowered:
        return "shopify"
    if "zendesk" in lowered:
        return "zendesk"
    return "manual"


def _normalize_lead_stage(value: str | None, status: str | None = None) -> str:
    stage = (value or "").strip().lower()
    if stage in LEAD_STAGE_ORDER:
        return stage
    status_norm = _normalize_lead_status(status or "new")
    mapping = {"new": "lead", "contacted": "contacted", "replied": "replied", "closed": "closed"}
    return mapping.get(status_norm, "lead")


def _read_outreach_queue() -> list[dict[str, Any]]:
    try:
        if not os.path.exists(OUTREACH_QUEUE_PATH):
            return []
        with open(OUTREACH_QUEUE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_outreach_queue(leads: list[dict[str, Any]]) -> None:
    with open(OUTREACH_QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)


def _lead_score(text: str, source: str = "manual") -> int:
    lowered = (text or "").lower()
    score = 0
    keyword_weights = {
        "zendesk": 2,
        "gorgias": 2,
        "support": 1,
        "customer support": 2,
        "tickets": 2,
        "refund": 2,
        "refunds": 2,
        "chargeback": 3,
        "complaint": 2,
        "cancel": 2,
        "shopify": 2,
        "manual": 1,
        "out of control": 3,
        "killing us": 3,
        "painful": 2,
        "swamped": 2,
        "overwhelmed": 2,
    }
    for key, weight in keyword_weights.items():
        if key in lowered:
            score += weight
    if (source or "").lower() in {"reddit", "twitter", "x", "shopify"}:
        score += 1
    return max(score, 1)


def _normalize_lead_status(value: str) -> str:
    status = (value or "new").strip().lower()
    return status if status in LEAD_STATUS_ORDER else "new"


def _generate_initial_lead_message(username: str, text: str) -> str:
    excerpt = " ".join((text or "").strip().split())
    excerpt = excerpt[:140] + ("..." if len(excerpt) > 140 else "")
    return (
        f"Hey — saw your post about support:\n\n"
        f"\"{excerpt}\"\n\n"
        f"I built a tool that prepares support decisions (refunds, replies, escalations) "
        f"but keeps you in control with approval.\n\n"
        f"It usually cuts support workload pretty hard without adding risk.\n\n"
        f"Happy to run a few of your tickets through it for free if you want to see it."
    )


def _generate_followup_message(lead: dict[str, Any]) -> str:
    text = str(lead.get("text", "") or "").lower()
    if "refund" in text or "charge" in text:
        angle = "Still dealing with refund volume?"
    elif "zendesk" in text or "ticket" in text:
        angle = "Still getting hit by ticket volume?"
    else:
        angle = "Just looping back on this"
    return (
        f"{angle}\n\n"
        f"Happy to show how Xalvion prepares the right support action "
        f"while keeping approval in your hands."
    )


def _build_lead_record(username: str, text: str, source: str = "manual") -> dict[str, Any]:
    now_iso = _crm_now_iso()
    normalized_source = _infer_lead_source(text, source)
    score = _lead_score(text, normalized_source)
    initial = _generate_initial_lead_message(username, text)
    follow_up_due = (_crm_now() + timedelta(days=2)).isoformat()
    return {
        "id": uuid.uuid4().hex,
        "username": (username or "").strip(),
        "text": (text or "").strip(),
        "source": normalized_source,
        "score": score,
        "status": "new",
        "stage": "lead",
        "value": 0.0,
        "converted_value": 0.0,
        "converted_at": None,
        "created_at": now_iso,
        "last_contacted": None,
        "follow_up_due": follow_up_due,
        "message": initial,
        "follow_up_message": _generate_followup_message({"text": text}),
        "messages": [
            {
                "type": "initial",
                "text": initial,
                "timestamp": now_iso,
            }
        ],
        "notes": [],
    }


def _serialize_lead(lead: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(lead or {})
    normalized["status"] = _normalize_lead_status(str(normalized.get("status", "new") or "new"))
    normalized["stage"] = _normalize_lead_stage(str(normalized.get("stage", "") or ""), normalized["status"])
    normalized["score"] = int(normalized.get("score", 1) or 1)
    normalized["source"] = _infer_lead_source(str(normalized.get("text", "") or ""), str(normalized.get("source", "manual") or "manual"))
    normalized["message"] = str(normalized.get("message", "") or "")
    normalized["follow_up_message"] = str(
        normalized.get("follow_up_message") or _generate_followup_message(normalized)
    )
    normalized["messages"] = list(normalized.get("messages") or [])
    normalized["notes"] = list(normalized.get("notes") or [])
    normalized["last_contacted"] = normalized.get("last_contacted")
    normalized["follow_up_due"] = normalized.get("follow_up_due")
    normalized["converted_at"] = normalized.get("converted_at")
    try:
        normalized["value"] = round(float(normalized.get("value", 0) or 0), 2)
    except Exception:
        normalized["value"] = 0.0
    try:
        normalized["converted_value"] = round(float(normalized.get("converted_value", 0) or 0), 2)
    except Exception:
        normalized["converted_value"] = 0.0
    return normalized




def _crm_day_bucket(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except Exception:
        return ""


def _is_due_followup(lead: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _crm_now()
    if _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new")) not in {"contacted", "replied", "demo"}:
        return False
    due_at = lead.get("follow_up_due")
    if not due_at:
        return False
    try:
        return datetime.fromisoformat(str(due_at)) <= now
    except Exception:
        return False


def _lead_hotness(lead: dict[str, Any]) -> int:
    stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new"))
    stage_weight = {"demo": 8, "replied": 6, "contacted": 3, "lead": 1, "closed": -2}.get(stage, 0)
    due_bonus = 2 if _is_due_followup(lead) else 0
    value_bonus = min(4, int(float(lead.get("value", 0) or 0) // 100))
    return int(lead.get("score", 0) or 0) + stage_weight + due_bonus + value_bonus


def _get_due_reminders(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = _crm_now()
    due = [lead for lead in leads if _is_due_followup(lead, now)]
    due.sort(key=lambda lead: (-_lead_hotness(lead), str(lead.get("follow_up_due") or "")))
    return due


def _get_daily_summary(leads: list[dict[str, Any]]) -> dict[str, Any]:
    today = _crm_now().date().isoformat()
    reminders = _get_due_reminders(leads)
    open_leads = [lead for lead in leads if _normalize_lead_status(str(lead.get("status", "new") or "new")) != "closed"]
    hottest = sorted(open_leads, key=lambda lead: (-_lead_hotness(lead), str(lead.get("created_at") or "")))[:3]

    new_today = sum(1 for lead in leads if _crm_day_bucket(lead.get("created_at")) == today)
    contacted_today = sum(1 for lead in leads if _crm_day_bucket(lead.get("last_contacted")) == today)
    closed_today = sum(1 for lead in leads if _crm_day_bucket(lead.get("converted_at")) == today or (_normalize_lead_status(str(lead.get("status", "new") or "new")) == "closed" and _crm_day_bucket(lead.get("last_contacted")) == today))
    closed_revenue_today = round(sum(float(lead.get("converted_value", 0) or 0) for lead in leads if _crm_day_bucket(lead.get("converted_at")) == today), 2)

    source_counts: dict[str, int] = {}
    for lead in leads:
        source = str(lead.get("source", "manual") or "manual")
        source_counts[source] = source_counts.get(source, 0) + 1
    best_source = "manual"
    if source_counts:
        best_source = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return {
        "date": today,
        "due_followups": len(reminders),
        "new_today": new_today,
        "contacted_today": contacted_today,
        "closed_today": closed_today,
        "closed_revenue_today": closed_revenue_today,
        "best_source": best_source,
        "hottest_open": [
            {
                "id": lead.get("id"),
                "username": lead.get("username"),
                "source": lead.get("source"),
                "status": lead.get("status"),
                "score": lead.get("score"),
                "follow_up_due": lead.get("follow_up_due"),
                "hotness": _lead_hotness(lead),
            }
            for lead in hottest
        ],
        "reminders": [
            {
                "id": lead.get("id"),
                "username": lead.get("username"),
                "status": lead.get("status"),
                "source": lead.get("source"),
                "follow_up_due": lead.get("follow_up_due"),
                "message": str(lead.get("follow_up_message") or lead.get("message") or ""),
            }
            for lead in reminders[:5]
        ],
    }


def _get_sorted_leads() -> list[dict[str, Any]]:
    leads = [_serialize_lead(item) for item in _read_outreach_queue()]
    stage_rank = {"demo": 0, "replied": 1, "contacted": 2, "lead": 3, "closed": 4}
    leads.sort(
        key=lambda item: (
            stage_rank.get(item.get("stage", item.get("status", "new")), 9),
            -(int(item.get("score", 0) or 0)),
            item.get("created_at", ""),
        )
    )
    return leads


def _get_lead_summary(leads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"new": 0, "contacted": 0, "replied": 0, "closed": 0, "due_followups": 0}
    now = _crm_now()
    for lead in leads:
        status = _normalize_lead_status(str(lead.get("status", "new") or "new"))
        counts[status] = counts.get(status, 0) + 1
        due_at = lead.get("follow_up_due")
        if _is_due_followup(lead, now) and due_at:
            counts["due_followups"] += 1
    return counts


def _stage_counts(leads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {stage: 0 for stage in LEAD_STAGE_ORDER}
    for lead in leads:
        stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new"))
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def _pct(num: float, den: float) -> float:
    return round((float(num) / float(den) * 100.0), 1) if den else 0.0


def _compute_revenue_metrics(leads: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [_serialize_lead(lead) for lead in leads]
    stage_counts = _stage_counts(normalized)
    total = len(normalized)
    contacted_plus = sum(1 for lead in normalized if _normalize_lead_stage(lead.get("stage"), lead.get("status")) in {"contacted", "replied", "demo", "closed"})
    replied_plus = sum(1 for lead in normalized if _normalize_lead_stage(lead.get("stage"), lead.get("status")) in {"replied", "demo", "closed"})
    demos = stage_counts.get("demo", 0)
    closed = stage_counts.get("closed", 0)
    revenue = round(sum(float(lead.get("converted_value", 0) or 0) for lead in normalized), 2)
    open_value = round(sum(float(lead.get("value", 0) or 0) for lead in normalized if _normalize_lead_stage(lead.get("stage"), lead.get("status")) != "closed"), 2)
    by_source_map: dict[str, dict[str, Any]] = {}
    for lead in normalized:
        source = str(lead.get("source", "manual") or "manual")
        stage = _normalize_lead_stage(lead.get("stage"), lead.get("status"))
        bucket = by_source_map.setdefault(source, {
            "source": source,
            "leads": 0,
            "contacted": 0,
            "replied": 0,
            "demo": 0,
            "closed": 0,
            "revenue": 0.0,
        })
        bucket["leads"] += 1
        if stage in {"contacted", "replied", "demo", "closed"}:
            bucket["contacted"] += 1
        if stage in {"replied", "demo", "closed"}:
            bucket["replied"] += 1
        if stage in {"demo", "closed"}:
            bucket["demo"] += 1
        if stage == "closed":
            bucket["closed"] += 1
            bucket["revenue"] = round(float(bucket["revenue"]) + float(lead.get("converted_value", 0) or 0), 2)
    by_source = []
    for bucket in by_source_map.values():
        contacted = bucket["contacted"]
        replied = bucket["replied"]
        demo = bucket["demo"]
        closed_count = bucket["closed"]
        leads_count = bucket["leads"]
        bucket["lead_to_contact_rate"] = _pct(contacted, leads_count)
        bucket["reply_rate"] = _pct(replied, contacted)
        bucket["closing_rate"] = _pct(closed_count, leads_count)
        bucket["win_rate"] = _pct(closed_count, demo)
        by_source.append(bucket)
    by_source.sort(key=lambda item: (-float(item.get("revenue", 0)), -float(item.get("win_rate", 0)), item.get("source", "")))
    best_source = by_source[0]["source"] if by_source else "manual"
    return {
        "totals": {
            "leads": total,
            "lead": stage_counts.get("lead", 0),
            "contacted": stage_counts.get("contacted", 0),
            "replied": stage_counts.get("replied", 0),
            "demo": stage_counts.get("demo", 0),
            "closed": closed,
            "contacted_or_beyond": contacted_plus,
            "replied_or_beyond": replied_plus,
            "revenue": revenue,
            "open_value": open_value,
            "reply_rate": _pct(replied_plus, contacted_plus),
            "closing_rate": _pct(closed, total),
            "lead_to_close_rate": _pct(closed, total),
            "win_rate": _pct(closed, demos),
        },
        "best_source": best_source,
        "by_source": by_source,
    }


def _stage_forecast_probability(stage: str) -> float:
    normalized = _normalize_lead_stage(stage, stage)
    return {
        "lead": 0.08,
        "contacted": 0.18,
        "replied": 0.38,
        "demo": 0.68,
        "closed": 1.0,
    }.get(normalized, 0.0)


def _compute_pipeline_forecast(leads: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [_serialize_lead(lead) for lead in leads]
    open_leads = [lead for lead in normalized if _normalize_lead_stage(lead.get("stage"), lead.get("status")) != "closed"]
    pipeline_value = round(sum(float(lead.get("value", 0) or 0) for lead in open_leads), 2)
    weighted_open_revenue = 0.0
    committed_revenue = 0.0
    stage_breakdown: dict[str, dict[str, Any]] = {}

    for lead in normalized:
        stage = _normalize_lead_stage(lead.get("stage"), lead.get("status"))
        nominal_value = float(lead.get("converted_value", 0) or 0) if stage == "closed" else float(lead.get("value", 0) or 0)
        probability = _stage_forecast_probability(stage)
        weighted_value = nominal_value * probability
        if stage != "closed":
            weighted_open_revenue += weighted_value
        else:
            committed_revenue += nominal_value

        bucket = stage_breakdown.setdefault(stage, {
            "stage": stage,
            "count": 0,
            "pipeline_value": 0.0,
            "weighted_value": 0.0,
            "probability": probability,
        })
        bucket["count"] += 1
        bucket["pipeline_value"] = round(float(bucket["pipeline_value"]) + nominal_value, 2)
        bucket["weighted_value"] = round(float(bucket["weighted_value"]) + weighted_value, 2)

    hottest_weighted = sorted(
        open_leads,
        key=lambda lead: (
            -(float(lead.get("value", 0) or 0) * _stage_forecast_probability(_normalize_lead_stage(lead.get("stage"), lead.get("status")))),
            -_lead_hotness(lead),
            str(lead.get("created_at") or ""),
        ),
    )[:5]

    return {
        "pipeline_value": round(pipeline_value, 2),
        "weighted_open_revenue": round(weighted_open_revenue, 2),
        "committed_revenue": round(committed_revenue, 2),
        "projected_total_revenue": round(committed_revenue + weighted_open_revenue, 2),
        "coverage_ratio": _pct(weighted_open_revenue, pipeline_value),
        "stage_breakdown": [
            stage_breakdown[key]
            for key in ["lead", "contacted", "replied", "demo", "closed"]
            if key in stage_breakdown
        ],
        "top_weighted_deals": [
            {
                "id": lead.get("id"),
                "username": lead.get("username"),
                "source": lead.get("source"),
                "stage": _normalize_lead_stage(lead.get("stage"), lead.get("status")),
                "value": round(float(lead.get("value", 0) or 0), 2),
                "weighted_value": round(float(lead.get("value", 0) or 0) * _stage_forecast_probability(_normalize_lead_stage(lead.get("stage"), lead.get("status"))), 2),
                "probability": round(_stage_forecast_probability(_normalize_lead_stage(lead.get("stage"), lead.get("status"))) * 100, 1),
            }
            for lead in hottest_weighted
        ],
    }


def _update_lead_status(lead_id: str, status: str | None = None, note: str | None = None, stage: str | None = None) -> dict[str, Any] | None:
    leads = _read_outreach_queue()
    now_iso = _crm_now_iso()
    updated_lead = None

    for lead in leads:
        if str(lead.get("id", "")) != str(lead_id):
            continue

        current_status = _normalize_lead_status(str(lead.get("status", "new") or "new"))
        current_stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), current_status)
        new_status = _normalize_lead_status(status or current_status)
        new_stage = _normalize_lead_stage(stage or current_stage, new_status)

        if stage == "lead":
            new_status = "new"
        elif stage == "contacted":
            new_status = "contacted"
        elif stage in {"replied", "demo"}:
            new_status = "replied"
        elif stage == "closed":
            new_status = "closed"

        lead["status"] = new_status
        lead["stage"] = new_stage

        if new_stage == "contacted":
            lead["last_contacted"] = now_iso
            lead["follow_up_due"] = (_crm_now() + timedelta(days=2)).isoformat()
            follow_text = _generate_followup_message(lead)
            lead["follow_up_message"] = follow_text
            history = list(lead.get("messages") or [])
            history.append({"type": "follow_up_scheduled", "text": follow_text, "timestamp": now_iso})
            lead["messages"] = history[-12:]
        elif new_stage == "replied":
            lead["last_contacted"] = now_iso
            lead["follow_up_due"] = (_crm_now() + timedelta(days=3)).isoformat()
        elif new_stage == "demo":
            lead["last_contacted"] = now_iso
            lead["follow_up_due"] = (_crm_now() + timedelta(days=4)).isoformat()
        elif new_stage == "closed":
            lead["follow_up_due"] = None
            lead["converted_at"] = lead.get("converted_at") or now_iso

        if note:
            notes = list(lead.get("notes") or [])
            notes.append({"text": str(note)[:300], "timestamp": now_iso})
            lead["notes"] = notes[-12:]

        updated_lead = _serialize_lead(lead)
        break

    if updated_lead is not None:
        _write_outreach_queue(leads)
    return updated_lead


@app.get("/leads")
def list_outreach_leads(user: User = Depends(require_authenticated_user)):
    leads = _get_sorted_leads()
    return {
        "items": leads,
        "summary": _get_lead_summary(leads),
        "daily_summary": _get_daily_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.get("/leads/followups")
def list_outreach_followups(user: User = Depends(require_authenticated_user)):
    leads = _get_sorted_leads()
    now = _crm_now()
    due: list[dict[str, Any]] = []
    for lead in leads:
        due_at = lead.get("follow_up_due")
        if lead.get("status") != "contacted" or not due_at:
            continue
        try:
            if datetime.fromisoformat(str(due_at)) <= now:
                due.append(lead)
        except Exception:
            continue
    return {
        "items": due,
        "summary": _get_lead_summary(leads),
        "daily_summary": _get_daily_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.post("/leads/add")
def add_outreach_lead(
    req: LeadAddRequest,
    user: User = Depends(require_authenticated_user),
):
    leads = _read_outreach_queue()
    record = _build_lead_record(req.username, req.text, req.source or "manual")
    leads.append(record)
    _write_outreach_queue(leads)
    all_leads = _get_sorted_leads()
    return {
        "lead": _serialize_lead(record),
        "items": all_leads,
        "summary": _get_lead_summary(all_leads),
        "daily_summary": _get_daily_summary(all_leads),
        "metrics": _compute_revenue_metrics(all_leads),
        "username": user.username,
    }


@app.post("/leads/{lead_id}/status")
def update_outreach_lead_status(
    lead_id: str,
    req: LeadStatusRequest,
    user: User = Depends(require_authenticated_user),
):
    updated = _update_lead_status(lead_id, req.status, req.note, req.stage)
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")

    all_leads = _get_sorted_leads()
    return {
        "lead": updated,
        "items": all_leads,
        "summary": _get_lead_summary(all_leads),
        "daily_summary": _get_daily_summary(all_leads),
        "metrics": _compute_revenue_metrics(all_leads),
        "username": user.username,
    }


def _snooze_lead_reminder(lead_id: str, days: int = 1, note: str | None = None) -> dict[str, Any] | None:
    leads = _read_outreach_queue()
    updated_lead = None
    now_iso = _crm_now_iso()
    new_due = (_crm_now() + timedelta(days=max(1, min(14, int(days or 1))))).isoformat()

    for lead in leads:
        if str(lead.get("id", "")) != str(lead_id):
            continue
        lead["follow_up_due"] = new_due
        if note:
            notes = list(lead.get("notes") or [])
            notes.append({"text": str(note)[:300], "timestamp": now_iso})
            lead["notes"] = notes[-12:]
        updated_lead = _serialize_lead(lead)
        break

    if updated_lead is not None:
        _write_outreach_queue(leads)
    return updated_lead


@app.get("/crm/daily-summary")
def crm_daily_summary(user: User = Depends(require_authenticated_user)):
    leads = _get_sorted_leads()
    return {
        "summary": _get_daily_summary(leads),
        "lead_summary": _get_lead_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.get("/crm/reminders")
def crm_reminders(user: User = Depends(require_authenticated_user)):
    leads = _get_sorted_leads()
    return {
        "items": _get_due_reminders(leads),
        "summary": _get_daily_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.post("/crm/reminders/{lead_id}/done")
def mark_crm_reminder_done(
    lead_id: str,
    req: LeadReminderRequest,
    user: User = Depends(require_authenticated_user),
):
    updated = _snooze_lead_reminder(lead_id, max(2, req.days), req.note or "Follow-up sent")
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    leads = _get_sorted_leads()
    return {
        "lead": updated,
        "items": leads,
        "summary": _get_lead_summary(leads),
        "daily_summary": _get_daily_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.post("/crm/reminders/{lead_id}/snooze")
def snooze_crm_reminder(
    lead_id: str,
    req: LeadReminderRequest,
    user: User = Depends(require_authenticated_user),
):
    updated = _snooze_lead_reminder(lead_id, req.days, req.note or f"Snoozed {req.days} day")
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    leads = _get_sorted_leads()
    return {
        "lead": updated,
        "items": leads,
        "summary": _get_lead_summary(leads),
        "daily_summary": _get_daily_summary(leads),
        "metrics": _compute_revenue_metrics(leads),
        "username": user.username,
    }


@app.get("/analytics/metrics")
def analytics_metrics(user: User = Depends(require_authenticated_user)):
    leads = _get_sorted_leads()
    return {
        "metrics": _compute_revenue_metrics(leads),
        "summary": _get_lead_summary(leads),
        "daily_summary": _get_daily_summary(leads),
        "username": user.username,
    }


@app.post("/leads/{lead_id}/convert")
def convert_outreach_lead(
    lead_id: str,
    req: LeadConvertRequest,
    user: User = Depends(require_authenticated_user),
):
    leads = _read_outreach_queue()
    now_iso = _crm_now_iso()
    updated = None
    for lead in leads:
        if str(lead.get("id", "")) != str(lead_id):
            continue
        lead["stage"] = "closed"
        lead["status"] = "closed"
        lead["converted_value"] = round(float(req.value or 0), 2)
        lead["value"] = round(max(float(lead.get("value", 0) or 0), float(req.value or 0)), 2)
        lead["converted_at"] = now_iso
        lead["follow_up_due"] = None
        lead["last_contacted"] = now_iso
        if req.note:
            notes = list(lead.get("notes") or [])
            notes.append({"text": str(req.note)[:300], "timestamp": now_iso})
            lead["notes"] = notes[-12:]
        updated = _serialize_lead(lead)
        break
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    _write_outreach_queue(leads)
    all_leads = _get_sorted_leads()
    return {
        "lead": updated,
        "items": all_leads,
        "summary": _get_lead_summary(all_leads),
        "daily_summary": _get_daily_summary(all_leads),
        "metrics": _compute_revenue_metrics(all_leads),
        "username": user.username,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)