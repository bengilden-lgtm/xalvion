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

print("[BOOT] APP.PY STARTING...", flush=True)

import asyncio
import json
import logging
import os
import re
import threading
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
    func,
    inspect,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agent import run_agent, local_fallback_reply, build_audit_summary_payload
from actions import (
    build_ticket as build_support_ticket,
    execution_requires_operator_gate,
    merge_impact_with_business_projection,
    system_decision,
    triage_ticket,
    HANDLED_ISSUE_TYPES,
    MAX_AUTO_REFUND_AMOUNT,
)
from db import Base, SessionLocal, engine, init_db
from memory import get_user_memory
from utils import normalize_ticket, safe_execute

try:
    from learning import learn_from_ticket
except Exception as _app_learning_imp_err:
    logging.getLogger("xalvion").warning(
        "learning.learn_from_ticket unavailable in app",
        exc_info=True,
    )

    def learn_from_ticket(ticket: dict[str, Any], decision: dict[str, Any], outcome: dict[str, Any]) -> None:
        raise RuntimeError("learning.learn_from_ticket unavailable") from _app_learning_imp_err

_METRICS_FALLBACK: dict[str, Any] = {
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

_dashboard_cache: dict[str, Any] = {}
_dashboard_cache_ts: float = 0.0
_DASHBOARD_TTL: float = 30.0

try:
    from analytics import get_metrics
except Exception as _get_metrics_imp_err:
    logging.getLogger("xalvion").warning(
        "analytics.get_metrics unavailable; dashboard metrics will use empty defaults",
        exc_info=True,
    )

    def get_metrics() -> dict[str, Any]:
        return dict(_METRICS_FALLBACK)

try:
    from outcome_store import (
        log_outcome as _log_real_outcome,
        get_outcome_stats,
        mark_ticket_reopened,
        mark_crm_closed,
        ensure_outcome_log_columns,
        ensure_outcome_columns,
        merge_audit_outcome_digest,
    )
except Exception as _outcome_store_imp_err:
    logging.getLogger("xalvion").warning(
        "outcome_store import failed; core outcome APIs will raise (stats stub returns zeros)",
        exc_info=True,
    )

    def _log_real_outcome(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def merge_audit_outcome_digest(
        audit: dict[str, Any] | None, outcome_key: str | None
    ) -> dict[str, Any] | None:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def get_outcome_stats() -> dict[str, Any]:
        return {
            "total": 0,
            "avg_outcome_quality": 0.0,
            "reopened_rate": 0.0,
            "crm_close_rate": 0.0,
            "avg_impact_score": 0.5,
            "excellent_rate": 0.0,
            "bad_rate": 0.0,
            "good_excellent_outcome_rate": 0.0,
        }

    def mark_ticket_reopened(_k: str) -> bool:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def mark_crm_closed(_k: str) -> bool:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def ensure_outcome_log_columns() -> None:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err

    def ensure_outcome_columns() -> None:
        raise RuntimeError("outcome_store module unavailable") from _outcome_store_imp_err


load_dotenv(override=True)

logger = logging.getLogger("xalvion.api")

STARTUP_ISSUES: list[str] = []
STARTUP_READY: bool = False

_db_issue_last_log: dict[str, float] = {}
DB_ISSUE_LOG_COOLDOWN_S = 60.0


def _log_throttled_db_issue(path_key: str, exc: BaseException) -> None:
    """Log DB/schema problems without per-request traceback spam."""
    now = time.time()
    last = _db_issue_last_log.get(path_key, 0.0)
    if now - last < DB_ISSUE_LOG_COOLDOWN_S:
        return
    _db_issue_last_log[path_key] = now
    logger.warning(
        "db_issue path=%s type=%s detail=%s",
        path_key,
        type(exc).__name__,
        str(exc)[:500],
    )

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
MAX_AUTO_REFUND = float(os.getenv("MAX_AUTO_REFUND", str(MAX_AUTO_REFUND_AMOUNT)))

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

# Unauthenticated operator preview (workspace): must match frontend GUEST_USAGE_LIMIT in app.js.
GUEST_PREVIEW_OPERATOR_LIMIT = int(os.getenv("GUEST_PREVIEW_OPERATOR_LIMIT", "3"))

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_SERVICES_DIR = os.path.join(BASE_DIR, "services")
INDEX_PATH = (
    os.path.join(_SERVICES_DIR, "index.html")
    if os.path.isfile(os.path.join(_SERVICES_DIR, "index.html"))
    else os.path.join(BASE_DIR, "index.html")
)
APP_JS_PATH = os.path.join(BASE_DIR, "app.js")
WORKSPACE_MODULES_JS_PATH = os.path.join(BASE_DIR, "workspace_modules.js")
STYLES_CSS_PATH = (
    os.path.join(_SERVICES_DIR, "styles.css")
    if os.path.isfile(os.path.join(_SERVICES_DIR, "styles.css"))
    else os.path.join(BASE_DIR, "styles.css")
)
LANDING_PATH = os.path.join(BASE_DIR, "landing.html")
FLUID_DIR = os.path.join(BASE_DIR, "fluid")
WORKSPACE_CLIENT_DIR = os.path.join(BASE_DIR, "workspace-client")

# =============================================================================
# FastAPI App + CORS
# =============================================================================

app = FastAPI(title="Xalvion Sovereign Brain")

if os.path.isdir(FLUID_DIR):
    app.mount("/fluid", StaticFiles(directory=FLUID_DIR), name="fluid")

if os.path.isdir(WORKSPACE_CLIENT_DIR):
    app.mount("/workspace-client", StaticFiles(directory=WORKSPACE_CLIENT_DIR), name="workspace_client")

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


class GuestPreviewUsage(Base):
    """Server-side tally for unauthenticated workspace preview runs (abuse hardening)."""

    __tablename__ = "guest_preview_usage"

    client_id = Column(String(80), primary_key=True)
    usage_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(String, nullable=False)


def _import_orm_submodules() -> None:
    """Import modules that register ORM classes on shared Base (required before create_all).
    Missing optional modules are logged instead of crashing process boot.
    """
    for module_name in ("analytics", "outcome_store", "persistence_layer", "state_store"):
        try:
            __import__(module_name)
        except Exception as exc:
            msg = f"optional_startup_import_failed:{module_name}:{type(exc).__name__}:{str(exc)[:180]}"
            STARTUP_ISSUES.append(msg)
            logger.warning(msg)


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


@app.on_event("startup")
def _startup_database() -> None:
    _import_orm_submodules()
    init_db()
    try:
        from security import assert_production_runtime_safety

        assert_production_runtime_safety()
        logger.info("runtime_security_check_passed")
    except RuntimeError as exc:
        logger.error("startup_security_check_failed detail=%s", exc)
        raise
    except Exception as exc:
        logger.warning("runtime_security_check_skipped detail=%s", str(exc)[:200])
    logger.info("DB schema ensured")
    print("DB schema ensured", flush=True)
    ensure_user_columns()
    try:
        ensure_outcome_log_columns()
    except Exception:
        pass
    try:
        ensure_outcome_columns()
    except Exception:
        pass
    try:
        from learning import sync_rules_to_brain

        sync_rules_to_brain()
        logger.info("rule_sync_complete")
    except Exception as _sync_exc:
        logger.warning("rule_sync_failed detail=%s", str(_sync_exc)[:200])


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
    # Customer-facing reply refined in workspace before approve (optional, capped).
    final_reply: str | None = None


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


# ── AUTH DEPENDENCY SELECTION GUIDE ────────────────────────────
# get_current_user()            Returns guest User if no valid token.
#                               Use for routes that intentionally
#                               support unauthenticated/preview access.
#
# require_authenticated_user()  Raises HTTP 401 if no valid token.
#                               Use for routes that require an account.
#
# require_admin()               Raises HTTP 403 unless ADMIN_USERNAME.
#
# Routes currently using get_current_user() that allow guest access:
#   POST /support, POST /analyze, GET /dashboard/summary,
#   GET /tickets, GET /billing/plans
#
# Review: confirm guest access is intentional for each of these.
# To lock a route down, change its dependency to
# require_authenticated_user().
# ────────────────────────────────────────────────────────────────
def get_current_user(
    authorization: str | None = Header(None),
) -> User:
    if not authorization:
        return User(username="guest", password="", usage=0, tier="free")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    token = authorization.split(" ", 1)[1].strip()
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found — this token no longer matches an account. Log in again.",
            )
        db.expunge(user)
        return user
    finally:
        db.close()


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
    billable_usage = max(0, usage - limit) if limit < 10**9 else 0
    within_included = usage if limit >= 10**9 else min(usage, limit)
    usage_pct = (usage / limit) if limit > 0 and limit < 10**9 else 0.0
    at_limit = bool(limit < 10**9 and usage >= limit)
    approaching_limit = bool(limit < 10**9 and usage_pct >= 0.75 and not at_limit)
    return {
        "tier": plan_name,
        "label": plan["label"],
        "usage": usage,
        "limit": limit,
        "remaining": remaining,
        "within_included": within_included,
        "billable_usage": billable_usage,
        "usage_pct": usage_pct,
        "at_limit": at_limit,
        "approaching_limit": approaching_limit,
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
    # NOTE: We never hard-block after plan limits. Overages are marked as billable usage
    # (front-end surfaces the notice), while rate limits still protect the service.
    _ = (plan_name, plan)


_guest_preview_lock = threading.Lock()


def normalize_guest_client_id(raw: str | None) -> str | None:
    """Stable id from X-Xalvion-Guest-Client; alphanumeric + ._- only."""
    s = (raw or "").strip()
    if not s or len(s) > 80:
        return None
    if not re.match(r"^[a-zA-Z0-9._-]+$", s):
        return None
    return s


def _guest_preview_exhausted_detail(used: int) -> dict[str, Any]:
    lim = int(GUEST_PREVIEW_OPERATOR_LIMIT)
    return {
        "code": "preview_exhausted",
        "message": "Preview runs are used up. Create a free account for monthly operator capacity and saved threads.",
        "usage": used,
        "limit": lim,
        "plan_limit": lim,
        "remaining": max(0, lim - used),
        "requires_signup": True,
        "requires_auth": True,
    }


def enforce_guest_preview_allow(client_id: str | None) -> None:
    """Do not hard-block guest preview usage; keep experience continuous.

    Abuse protection remains via `check_rate_limit` and the guest preview counter is still incremented
    so the UI can surface upgrade nudges and billable overage semantics.
    """
    gid = normalize_guest_client_id(client_id)
    if not gid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "preview_client_required",
                "message": "Reload the workspace and try again (preview client id missing).",
            },
        )
    with _guest_preview_lock:
        with db_session() as db:
            row = db.query(GuestPreviewUsage).filter(GuestPreviewUsage.client_id == gid).first()
            _ = int(row.usage_count) if row else 0


def bump_guest_preview_usage(client_id: str | None) -> dict[str, Any] | None:
    """Increment successful guest preview usage; returns entitlement slice for API payloads."""
    gid = normalize_guest_client_id(client_id)
    if not gid:
        return None
    now = _now_iso()
    with _guest_preview_lock:
        with db_session() as db:
            row = db.query(GuestPreviewUsage).filter(GuestPreviewUsage.client_id == gid).first()
            if not row:
                row = GuestPreviewUsage(client_id=gid, usage_count=0, updated_at=now)
                db.add(row)
                db.flush()
            row.usage_count = int(row.usage_count or 0) + 1
            row.updated_at = now
            db.commit()
            used = int(row.usage_count)
            lim = int(GUEST_PREVIEW_OPERATOR_LIMIT)
            rem = max(0, lim - used)
            return {
                "usage": used,
                "limit": lim,
                "plan_limit": lim,
                "remaining": rem,
                "preview_exhausted": rem <= 0,
            }

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


def build_agent_meta(
    req: SupportRequest,
    user: User,
    db: Session | None = None,
    *,
    operator_mode: str | None = None,
) -> dict[str, Any]:
    plan_name = get_plan_name(user)
    if operator_mode is not None:
        op_mode = _safe_op_mode(operator_mode)
    elif db is not None:
        op_mode = get_operator_mode(db)
    else:
        op_mode = "balanced"
    return {
        "sentiment": req.sentiment if req.sentiment is not None else 5,
        "ltv": req.ltv if req.ltv is not None else 0,
        "order_status": req.order_status if req.order_status is not None else "unknown",
        "plan_tier": plan_name,
        "priority_routing": get_plan_config(plan_name)["priority_routing"],
        "payment_intent_id": (req.payment_intent_id or "").strip(),
        "charge_id": (req.charge_id or "").strip(),
        "operator_mode": op_mode,
        "channel": _safe_channel(req.channel),
        "source": _safe_source(req.source),
    }


try:
    from services import ticket_service

    create_ticket_record = ticket_service.create_ticket_record
    update_ticket_from_result = ticket_service.update_ticket_from_result
    log_action = ticket_service.log_action
    serialize_ticket = ticket_service.serialize_ticket
    serialize_ticket_with_log = ticket_service.serialize_ticket_with_log
except Exception as exc:
    STARTUP_ISSUES.append(f"ticket_service_import_failed:{type(exc).__name__}:{str(exc)[:180]}")
    logger.warning("ticket_service import failed; using local compatibility helpers", exc_info=True)

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


def _attach_trust_layer(result: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Build or enrich audit_summary and merge verified outcome digest (additive)."""
    key = (str(result.get("outcome_key") or "")).strip() or None
    audit = result.get("audit_summary")
    if not isinstance(audit, dict) or not audit:
        try:
            dec = dict(result.get("decision") or {})
            audit = build_audit_summary_payload(
                proposed_action={
                    **dec,
                    "action": str(result.get("action", dec.get("action", "none")) or "none"),
                    "amount": float(result.get("amount", dec.get("amount", 0)) or 0),
                    "reason": str(result.get("reason", dec.get("reason", "")) or ""),
                    "requires_approval": bool(dec.get("requires_approval", False)),
                },
                executed={
                    "action": str(result.get("action", "none") or "none"),
                    "amount": float(result.get("amount", 0) or 0),
                    "tool_status": str(result.get("tool_status", "no_action") or "no_action"),
                    "tool_result": result.get("tool_result") if isinstance(result.get("tool_result"), dict) else {},
                },
                outcome_key=key,
                human_approved=False,
                issue_type=str(result.get("issue_type", "general_support") or "general_support"),
            )
        except Exception:
            audit = None
    merged = merge_audit_outcome_digest(audit, key)
    return merged, key


def serialize_support_result(
    result: dict[str, Any],
    user: User,
    *,
    guest_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if guest_preview:
        usage_summary = {
            "tier": "free",
            "label": "Preview",
            "usage": int(guest_preview.get("usage", 0) or 0),
            "limit": int(guest_preview.get("limit", GUEST_PREVIEW_OPERATOR_LIMIT) or GUEST_PREVIEW_OPERATOR_LIMIT),
            "remaining": int(guest_preview.get("remaining", 0) or 0),
            "dashboard_access": get_plan_config("free")["dashboard_access"],
            "priority_routing": False,
        }
        plan_limit_val = int(guest_preview.get("plan_limit", usage_summary["limit"]) or usage_summary["limit"])
        usage_val = int(guest_preview.get("usage", 0) or 0)
        remaining_val = int(guest_preview.get("remaining", 0) or 0)
    else:
        usage_summary = get_usage_summary(user)
        plan_limit_val = int(usage_summary["limit"])
        usage_val = int(usage_summary["usage"])
        remaining_val = max(
            0,
            get_plan_config(get_public_plan_name(user))["monthly_limit"] - usage_summary["usage"],
        )
    billable_usage_val = max(0, usage_val - plan_limit_val) if plan_limit_val < 10**9 else 0
    within_included_val = usage_val if plan_limit_val >= 10**9 else min(usage_val, plan_limit_val)
    usage_pct_val = (usage_val / plan_limit_val) if plan_limit_val > 0 and plan_limit_val < 10**9 else 0.0
    at_limit_val = bool(plan_limit_val < 10**9 and usage_val >= plan_limit_val)
    approaching_limit_val = bool(plan_limit_val < 10**9 and usage_pct_val >= 0.75 and not at_limit_val)
    tool_result = result.get("tool_result") or {}
    impact = result.get("impact") or {}
    reply = result.get("reply") or result.get("response") or result.get("final") or "No response"
    _tool_st = str(result.get("tool_status", tool_result.get("status", "")) or "").lower()
    _needs_appr = bool((result.get("decision") or {}).get("requires_approval", False)) or _tool_st in {
        "pending_approval",
        "manual_review",
    }
    execution = dict(
        result.get("execution")
        or {
            "action": result.get("action", "none"),
            "amount": result.get("amount", 0),
            "status": result.get("tool_status", tool_result.get("status", "unknown")),
            "auto_resolved": bool(impact.get("auto_resolved", False)),
            "requires_approval": _needs_appr,
        }
    )
    execution["requires_approval"] = bool(execution.get("requires_approval", False)) or _needs_appr
    trust_audit, outcome_correlation_key = _attach_trust_layer(result)

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
        "action_result": tool_result,
        "impact": impact,
        "execution": execution,
        "decision": result.get("decision", {}),
        "output": result.get("output", {}),
        "meta": result.get("meta", {}),
        "triage": result.get("triage", {}),
        "history": result.get("history", {}),
        "runtime_ticket": result.get("runtime_ticket", {}),
        "username": str(getattr(user, "username", "guest") or "guest"),
        "tier": usage_summary["tier"],
        "plan_limit": plan_limit_val,
        "usage": usage_val,
        "remaining": remaining_val,
        "within_included": within_included_val,
        "billable_usage": billable_usage_val,
        "usage_pct": usage_pct_val,
        "at_limit": at_limit_val,
        "approaching_limit": approaching_limit_val,
        "entitlement": {
            "kind": "guest_preview" if guest_preview else "account",
            "usage": usage_val,
            "limit": plan_limit_val,
            "remaining": remaining_val,
            "within_included": within_included_val,
            "billable_usage": billable_usage_val,
            "usage_pct": usage_pct_val,
            "at_limit": at_limit_val,
            "approaching_limit": approaching_limit_val,
            "preview_exhausted": bool(guest_preview.get("preview_exhausted")) if guest_preview else False,
            "requires_signup": bool(guest_preview and guest_preview.get("preview_exhausted")),
        },
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
        "stripe_account_id": getattr(user, "stripe_account_id", None),
        "decision_state": "pending_decision"
        if bool((result.get("decision") or {}).get("requires_approval", False))
        else "approved",
        "decision_explanation": result.get("decision_explanation"),
        "decision_explainability": result.get("decision_explainability"),
        "execution_tier": str(result.get("execution_tier") or "approval_required"),
        "outcome_key": outcome_correlation_key,
        "audit_summary": trust_audit,
    }

# =============================================================================
# 10. BILLING HELPERS (STRIPE) — implemented in services/stripe_service.py
# =============================================================================


def apply_real_actions(result: dict[str, Any], req: SupportRequest, user: User) -> dict[str, Any]:
    from services import stripe_service

    result = dict(result or {})
    if str(result.get("action", "none") or "none").lower() != "refund":
        return result

    refund_result = stripe_service.execute_real_refund(
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
    result["response"] = stripe_service.rewrite_refund_failure_message(failure)
    result["final"] = result["response"]
    return result


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
        "risk_level": str((result.get("decision") or {}).get("risk_level", "medium") or "medium"),
    }
    outcome = dict(result.get("impact") or {})
    if not outcome:
        outcome = merge_impact_with_business_projection(
            runtime_ticket,
            decision,
            confidence=float(result.get("confidence", 0.9) or 0.9),
        )
    safe_execute(learn_from_ticket, runtime_ticket, decision, outcome)


def check_requires_approval(action: str, amount: float) -> bool:
    return execution_requires_operator_gate(action, amount)


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
    ok = (str(pending.get("outcome_key") or result.get("outcome_key") or "")).strip() or None
    pending["outcome_key"] = ok
    issue = str(pending.get("issue_type", "general_support") or "general_support")
    try:
        pending["audit_summary"] = merge_audit_outcome_digest(
            build_audit_summary_payload(
                proposed_action=dict(pending.get("decision") or {}),
                executed={
                    "action": str(pending.get("action", "none") or "none"),
                    "amount": float(pending.get("amount", 0) or 0),
                    "tool_status": str(pending.get("tool_status", "pending_approval") or "pending_approval"),
                    "tool_result": pending.get("tool_result") if isinstance(pending.get("tool_result"), dict) else {},
                },
                outcome_key=ok,
                human_approved=False,
                issue_type=issue,
            ),
            ok,
        )
    except Exception:
        pass
    return pending


def build_ticket_response_payload(
    ticket: Ticket,
    log: ActionLog | None = None,
    *,
    db: Session | None = None,
) -> dict[str, Any]:
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
        "status": str(ticket.status or "new"),
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
        "ticket": serialize_ticket_with_log(ticket, db) if db is not None else {**serialize_ticket(ticket), "action_log": None},
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
        try:
            _log_real_outcome(
                outcome_key="approve:{}:{}".format(
                    getattr(ticket, "id", ""),
                    proposed_action,
                ),
                user_id=str(getattr(ticket, "username", "") or ""),
                action=proposed_action,
                amount=proposed_amount,
                issue_type=str(
                    getattr(ticket, "issue_type", "general_support")
                    or "general_support"
                ),
                tool_result={"status": "approved"},
                auto_resolved=False,
                approved_by_human=True,
            )
        except Exception as _log_exc:
            logger.warning(
                "outcome_log_failed action=%s ticket_id=%s detail=%s",
                proposed_action,
                getattr(ticket, "id", ""),
                str(_log_exc)[:200],
            )
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


def run_support(req: SupportRequest, user: User, guest_client_id: str | None = None) -> dict[str, Any]:
    enforce_plan_limits(user)
    if str(getattr(user, "username", "") or "").strip().lower() == "guest":
        enforce_guest_preview_allow(guest_client_id)

    with db_session() as db:
        try:
            created = create_ticket_record(db, user, req)
            ticket_id = int(created.id)
        except SQLAlchemyError as exc:
            try:
                db.rollback()
            except Exception:
                pass
            _log_throttled_db_issue("support_ticket_persist", exc)
            raise HTTPException(
                status_code=503,
                detail="Support ticketing database is temporarily unavailable. Please try again shortly.",
            ) from None

    logger.info(
        "support_db_released_after_ticket_create ticket_id=%s user=%s",
        ticket_id,
        getattr(user, "username", "") or "?",
    )

    with db_session() as db:
        runtime_ticket = build_runtime_ticket(req, user, db)

    shadow_decision = safe_execute(system_decision, runtime_ticket)
    if not isinstance(shadow_decision, dict) or shadow_decision.get("__xalvion_exec_error__"):
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
        msg = (req.message or "").lower()
        issue_type_rt = str(runtime_ticket.get("issue_type", "general_support") or "general_support")

        shipping_keys = (
            "where is my order",
            "my order",
            "tracking",
            "package",
            "delivery",
            "late",
        )
        damaged_keys = ("damaged", "broken", "arrived damaged")

        _billing_fast_types = HANDLED_ISSUE_TYPES - {"shipping_issue", "damaged_order"}
        billing_msg_keys = (
            "charged twice",
            "double charge",
            "duplicate charge",
            "billed twice",
            "overcharged",
            "over charged",
            "wrong charge",
        )

        is_damaged = (issue_type_rt in HANDLED_ISSUE_TYPES and issue_type_rt == "damaged_order") or any(
            k in msg for k in damaged_keys
        )
        is_billing = issue_type_rt in _billing_fast_types or any(k in msg for k in billing_msg_keys)
        is_shipping = (issue_type_rt in HANDLED_ISSUE_TYPES and issue_type_rt == "shipping_issue") or any(
            k in msg for k in shipping_keys
        )

        triage_rt = runtime_ticket.get("triage") or {}
        risk_from_ctx = str(
            shadow_decision.get("risk_level", triage_rt.get("risk_level", "medium")) or "medium"
        )
        order_info = {
            "status": str(runtime_ticket.get("order_status", "unknown") or "unknown"),
            "tracking": str(runtime_ticket.get("tracking", "") or ""),
            "eta": str(runtime_ticket.get("eta", "") or ""),
        }

        if is_damaged:
            ticket_local = dict(runtime_ticket)
            ticket_local["issue_type"] = "damaged_order"
            dam_act = str(shadow_decision.get("action", "review") or "review")
            if dam_act == "none":
                dam_act = "review"
            planned_action = {
                "action": dam_act,
                "amount": float(shadow_decision.get("amount", 0) or 0),
                "reason": str(shadow_decision.get("reason", "") or ""),
                "queue": str(shadow_decision.get("queue", "escalated") or "escalated"),
                "priority": str(shadow_decision.get("priority", "high") or "high"),
                "risk_level": risk_from_ctx,
                "requires_approval": False,
            }
            local_result = local_fallback_reply(ticket_local, planned_action, order_info, req.message)
            local_result["mode"] = "local_fast_path"
            local_result["issue_type"] = "damaged_order"
            local_result["tool_result"] = {
                "status": "local_fast_path",
                "type": "escalation",
            }
            local_result["tool_status"] = "local_fast_path"
            result = local_result
        elif is_billing:
            ticket_local = dict(runtime_ticket)
            if issue_type_rt in _billing_fast_types:
                it = issue_type_rt
            elif any(k in msg for k in billing_msg_keys):
                it = "billing_duplicate_charge"
            elif "refund" in msg:
                it = "refund_request"
            else:
                it = "billing_issue"
            ticket_local["issue_type"] = it
            q_default = "refund_risk" if it in {"billing_duplicate_charge", "refund_request"} else "waiting"
            planned_action = {
                "action": "none",
                "amount": 0,
                "reason": str(shadow_decision.get("reason", "") or ""),
                "queue": str(shadow_decision.get("queue", q_default) or q_default),
                "priority": str(shadow_decision.get("priority", "high") or "high"),
                "risk_level": risk_from_ctx,
                "requires_approval": False,
            }
            local_result = local_fallback_reply(ticket_local, planned_action, order_info, req.message)
            local_result["mode"] = "local_fast_path"
            local_result["issue_type"] = it
            local_result["tool_result"] = {
                "status": "local_fast_path",
                "type": "billing",
            }
            local_result["tool_status"] = "local_fast_path"
            result = local_result
        elif is_shipping:
            ticket_local = dict(runtime_ticket)
            ticket_local["issue_type"] = "shipping_issue"
            planned_action = {
                "action": str(shadow_decision.get("action", "none") or "none"),
                "amount": float(shadow_decision.get("amount", 0) or 0),
                "reason": str(shadow_decision.get("reason", "") or ""),
                "queue": str(shadow_decision.get("queue", "waiting") or "waiting"),
                "priority": str(shadow_decision.get("priority", "medium") or "medium"),
                "risk_level": risk_from_ctx,
                "requires_approval": False,
            }
            local_result = local_fallback_reply(ticket_local, planned_action, order_info, req.message)
            local_result["mode"] = "local_fast_path"
            local_result["issue_type"] = "shipping_issue"
            local_result["tool_result"] = {
                "status": "local_fast_path",
                "type": "tracking",
            }
            local_result["tool_status"] = "local_fast_path"
            result = local_result
        else:
            op_mode = str(runtime_ticket.get("operator_mode", "balanced") or "balanced")
            logger.info(
                "support_agent_phase_start ticket_id=%s user=%s (db not held during LLM)",
                ticket_id,
                getattr(user, "username", "") or "?",
            )
            result = run_agent(
                req.message,
                user_id=str(getattr(user, "username", "guest") or "guest"),
                meta=build_agent_meta(req, user, operator_mode=op_mode),
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

        merged_impact = merge_impact_with_business_projection(
            runtime_ticket,
            {
                "action": str(result.get("action", "none") or "none"),
                "amount": float(result.get("amount", 0) or 0),
            },
            confidence=float(result.get("confidence", 0.9) or 0.9),
        )
        agent_impact = result.get("impact") if isinstance(result.get("impact"), dict) else {}
        impact = {**agent_impact, **merged_impact}
        result = hydrate_result_with_engine_context(
            result,
            runtime_ticket=runtime_ticket,
            hard_decision=shadow_decision,
            impact=impact,
            user=user,
        )
        try:
            apply_learning_feedback(runtime_ticket, result)
        except Exception as _learn_exc:
            logger.warning(
                "learning_feedback_failed ticket_id=%s detail=%s",
                ticket_id,
                str(_learn_exc)[:200],
            )

        logger.info(
            "support_db_persist_begin ticket_id=%s user=%s",
            ticket_id,
            getattr(user, "username", "") or "?",
        )
        with db_session() as db:
            t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not t:
                raise RuntimeError("ticket row missing at persist")
            update_ticket_from_result(db, t, result)
            action_entry = log_action(
                db,
                username=str(getattr(user, "username", "unknown")),
                ticket_id=t.id,
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

            ser_user: User = user
            guest_preview_snapshot: dict[str, Any] | None = None
            if hasattr(user, "usage") and getattr(user, "username", "") not in {"dev_user", "guest"}:
                u_row = db.query(User).filter(User.username == user.username).first()
                if u_row:
                    u_row.usage = int(u_row.usage or 0) + 1
                    db.commit()
                    db.refresh(u_row)
                    ser_user = u_row
            elif str(getattr(user, "username", "") or "").strip().lower() == "guest":
                guest_preview_snapshot = bump_guest_preview_usage(guest_client_id)

            serialized = serialize_support_result(result, ser_user, guest_preview=guest_preview_snapshot)
            serialized["ticket"] = serialize_ticket_with_log(t, db)
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

        logger.info(
            "support_db_persist_done ticket_id=%s user=%s",
            ticket_id,
            getattr(user, "username", "") or "?",
        )
        return serialized

    except HTTPException:
        raise

    except Exception as exc:
        with db_session() as db:
            try:
                tt = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if tt:
                    tt.status = "failed"
                    tt.queue = "escalated"
                    tt.internal_note = f"Pipeline error: {str(exc)[:500]}"
                    tt.updated_at = _now_iso()
                    db.commit()
            except Exception:
                pass

        ticket_snapshot: dict[str, Any]
        with db_session() as db:
            tt2 = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            ticket_snapshot = serialize_ticket(tt2) if tt2 else {"id": ticket_id}

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
            "outcome_key": None,
            "audit_summary": {
                "version": 1,
                "trace": [
                    "System: Request could not be completed automatically.",
                    "Execution: Escalated for manual review — no billing motion applied.",
                ],
                "approval": {"required": False, "human_confirmed": False},
                "outcome": {"known": False, "summary": None, "tier": None, "success": None},
            },
            "tier": plan,
            "plan_limit": get_plan_config(plan)["monthly_limit"],
            "usage": int(getattr(user, "usage", 0) or 0),
            "remaining": max(0, get_plan_config(plan)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
            "ticket": ticket_snapshot,
            "operator_mode": runtime_ticket.get("operator_mode", "balanced"),
            "shadow_decision": shadow_decision,
            "runtime_ticket": runtime_ticket,
        }


def run_support_for_username(
    req: SupportRequest,
    username: str,
    guest_client_id: str | None = None,
) -> dict[str, Any]:
    with db_session() as db:
        if username and username != "guest":
            row = db.query(User).filter(User.username == username).first()
            if not row:
                user = User(username="guest", password="", usage=0, tier="free")
            else:
                db.expunge(row)
                user = row
        else:
            user = User(username="guest", password="", usage=0, tier="free")
    return run_support(req, user, guest_client_id=guest_client_id)

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


@app.get("/workspace_modules.js")
def serve_workspace_modules_js():
    if os.path.exists(WORKSPACE_MODULES_JS_PATH):
        return FileResponse(WORKSPACE_MODULES_JS_PATH, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="workspace_modules.js not found")


@app.get("/styles.css")
def serve_styles_css():
    if os.path.exists(STYLES_CSS_PATH):
        return FileResponse(STYLES_CSS_PATH, media_type="text/css; charset=utf-8")
    raise HTTPException(status_code=404, detail="styles.css not found")


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
    """Shallow liveness: process is up (use /health/deep for readiness)."""
    return {"status": "ok", "service": "xalvion-sovereign-brain"}


@app.get("/health/deep")
def health_deep(db: Session = Depends(get_db)):
    from sqlalchemy import text as _text

    checks: dict[str, Any] = {}
    mode = (os.getenv("ENVIRONMENT", "development") or "development").strip()
    checks["mode"] = mode

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

    env_lower = mode.lower()
    if env_lower == "production":
        raw_jwt = os.getenv("JWT_SECRET")
        checks["jwt_secret"] = "configured" if (raw_jwt and raw_jwt.strip()) else "missing"
    else:
        checks["jwt_secret"] = "n/a"

    checks["stripe"] = "configured" if STRIPE_KEY else "missing"
    checks["openai"] = "configured" if os.getenv("OPENAI_API_KEY", "").strip() else "missing"

    degraded = any(isinstance(v, str) and v.startswith("error") for v in checks.values())
    if checks.get("jwt_secret") == "missing":
        degraded = True

    checks["status"] = "degraded" if degraded else "ok"
    checks["service"] = "xalvion-sovereign-brain"
    return checks


# =============================================================================
# ROUTER MODULES (auth, billing, dashboard, support)
# =============================================================================

for _router_mod, _router_label in (
    ("routes.auth", "auth"),
    ("routes.billing", "billing"),
    ("routes.dashboard", "dashboard"),
    ("routes.support", "support"),
):
    try:
        _module = __import__(_router_mod, fromlist=["router"])
        app.include_router(_module.router)
    except Exception as exc:
        STARTUP_ISSUES.append(f"router_import_failed:{_router_label}:{type(exc).__name__}:{str(exc)[:180]}")
        logger.warning("router import failed for %s", _router_label, exc_info=True)


# =============================================================================
# FALLBACK ROUTES (workspace-critical)
# =============================================================================
# The live workspace frontend depends on these endpoints being present. In some
# deployments, optional router modules may not ship; these fallback endpoints
# keep auth, billing, integrations, and preview gating reliable.


def _guest_preview_snapshot(client_id: str | None) -> dict[str, Any] | None:
    gid = normalize_guest_client_id(client_id)
    if not gid:
        return None
    with db_session() as db:
        row = db.query(GuestPreviewUsage).filter(GuestPreviewUsage.client_id == gid).first()
        used = int(row.usage_count) if row else 0
    lim = int(GUEST_PREVIEW_OPERATOR_LIMIT)
    rem = max(0, lim - used)
    return {
        "usage": used,
        "limit": lim,
        "plan_limit": lim,
        "remaining": rem,
        "preview_exhausted": rem <= 0,
    }


@app.post("/signup")
def signup(req: AuthRequest, db: Session = Depends(get_db)):
    username = validate_username(req.username)
    password = validate_password(req.password)

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=username, password=hash_password(password), usage=0, tier="free")
    db.add(user)
    db.commit()
    token = create_token(username)
    return {
        "token": token,
        "username": username,
        "tier": get_public_plan_name(user),
        "usage": 0,
        "limit": get_plan_config("free")["monthly_limit"],
        "remaining": get_plan_config("free")["monthly_limit"],
    }


@app.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    username = validate_username(req.username)
    password = (req.password or "").strip()

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, str(user.password or "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(username)
    usage = get_usage_summary(user)
    return {
        "token": token,
        "username": username,
        "tier": get_public_plan_name(user),
        "usage": usage["usage"],
        "limit": usage["limit"],
        "remaining": usage["remaining"],
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
        "stripe_account_id": str(getattr(user, "stripe_account_id", "") or ""),
        "stripe_livemode": bool(getattr(user, "stripe_livemode", 0)),
    }


@app.get("/me")
def me(
    user: User = Depends(get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(get_db),
):
    if getattr(user, "username", "") in {"", "guest"}:
        snap = _guest_preview_snapshot(guest_client_id)
        usage = {
            "tier": "free",
            "label": "Free",
            "usage": int(snap["usage"]) if snap else 0,
            "limit": int(snap["limit"]) if snap else int(GUEST_PREVIEW_OPERATOR_LIMIT),
            "remaining": int(snap["remaining"]) if snap else int(GUEST_PREVIEW_OPERATOR_LIMIT),
            "dashboard_access": "basic",
            "priority_routing": False,
        }
        return {
            "ok": True,
            "authenticated": False,
            "username": "",
            "tier": "free",
            "usage": usage["usage"],
            "limit": usage["limit"],
            "remaining": usage["remaining"],
            "guest_preview": snap,
            "stripe_connected": False,
            "stripe_account_id": "",
            "stripe_livemode": False,
        }

    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    usage = get_usage_summary(db_user)
    return {
        "ok": True,
        "authenticated": True,
        "username": db_user.username,
        "tier": get_public_plan_name(db_user),
        "usage": usage["usage"],
        "limit": usage["limit"],
        "remaining": usage["remaining"],
        "stripe_connected": bool(getattr(db_user, "stripe_connected", 0)),
        "stripe_account_id": str(getattr(db_user, "stripe_account_id", "") or ""),
        "stripe_livemode": bool(getattr(db_user, "stripe_livemode", 0)),
    }


@app.get("/billing/plans")
def billing_plans(
    user: User = Depends(get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    tier = get_public_plan_name(user)
    payload = build_upgrade_payload(tier)
    if getattr(user, "username", "") in {"", "guest"}:
        payload["guest_preview"] = _guest_preview_snapshot(guest_client_id)
    return payload


@app.post("/billing/upgrade")
def billing_upgrade(req: UpgradeRequest, user: User = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    desired = (req.tier or "").strip().lower()
    current = get_public_plan_name(user)
    from services import stripe_service

    stripe_service.validate_upgrade_request(desired, current)
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    session = stripe_service.create_checkout_session_for_user(db_user, desired)
    return {"ok": True, "checkout_url": getattr(session, "url", ""), "session_id": getattr(session, "id", "")}


@app.get("/integrations/status")
def integrations_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if getattr(user, "username", "") in {"", "guest"}:
        return {"ok": True, "stripe_connected": False, "stripe_account_id": "", "stripe_livemode": False}
    row = db.query(User).filter(User.username == user.username).first()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return {
        "ok": True,
        "stripe_connected": bool(getattr(row, "stripe_connected", 0)),
        "stripe_account_id": str(getattr(row, "stripe_account_id", "") or ""),
        "stripe_livemode": bool(getattr(row, "stripe_livemode", 0)),
        "stripe_scope": str(getattr(row, "stripe_scope", "") or ""),
    }


@app.get("/integrations/stripe/connect")
def stripe_connect(user: User = Depends(require_authenticated_user)):
    if not STRIPE_CONNECT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Stripe Connect client id not configured")
    from services import stripe_service

    state_token = create_stripe_state(user.username)
    url = stripe_service.build_stripe_connect_authorize_url(
        client_id=STRIPE_CONNECT_CLIENT_ID,
        redirect_uri=STRIPE_CONNECT_REDIRECT_URI,
        state=state_token,
        scope="read_write",
    )
    return {"ok": True, "url": url}


@app.get("/integrations/stripe/callback")
def stripe_connect_callback(code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    username = decode_stripe_state(state or "")
    if not username:
        return RedirectResponse(url=f"{FRONTEND_URL}?surface=integrations&stripe=state_error")
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}?surface=integrations&stripe=missing_code")
    if not STRIPE_KEY:
        return RedirectResponse(url=f"{FRONTEND_URL}?surface=integrations&stripe=not_configured")

    try:
        resp = stripe.OAuth.token(grant_type="authorization_code", code=code)
        acct_id = str(resp.get("stripe_user_id") or "")
        scope = str(resp.get("scope") or "")
        livemode = bool(resp.get("livemode", False))
        if not acct_id:
            raise RuntimeError("No stripe_user_id returned from Stripe")
    except Exception:
        return RedirectResponse(url=f"{FRONTEND_URL}?surface=integrations&stripe=oauth_error")

    user = db.query(User).filter(User.username == username).first()
    if user:
        user.stripe_connected = 1
        user.stripe_account_id = acct_id
        user.stripe_scope = scope
        user.stripe_livemode = 1 if livemode else 0
        db.commit()

    return RedirectResponse(url=f"{FRONTEND_URL}?surface=integrations&stripe=connected")


@app.post("/integrations/stripe/disconnect")
def stripe_disconnect(user: User = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    row = db.query(User).filter(User.username == user.username).first()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    row.stripe_connected = 0
    row.stripe_account_id = None
    row.stripe_scope = None
    row.stripe_livemode = 0
    db.commit()
    return {"ok": True}


@app.post("/support")
def support(
    req: SupportRequest,
    user: User = Depends(get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    username = getattr(user, "username", "") or "guest"
    return JSONResponse(
        content=run_support_for_username(req, username=username, guest_client_id=guest_client_id),
        media_type="application/json; charset=utf-8",
    )


@app.post("/support/stream")
async def support_stream(
    req: SupportRequest,
    user: User = Depends(get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    username = getattr(user, "username", "") or "guest"
    result = await run_in_threadpool(run_support_for_username, req, username, guest_client_id)
    return StreamingResponse(stream_support_events(result), media_type="text/event-stream")


@app.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
    db: Session = Depends(get_db),
):
    usage = get_usage_summary(user)
    if getattr(user, "username", "") in {"", "guest"}:
        snap = _guest_preview_snapshot(guest_client_id) or {}
        usage = {
            "tier": "free",
            "label": "Free",
            "usage": int(snap.get("usage", 0) or 0),
            "limit": int(snap.get("limit", GUEST_PREVIEW_OPERATOR_LIMIT) or GUEST_PREVIEW_OPERATOR_LIMIT),
            "remaining": int(snap.get("remaining", 0) or 0),
            "dashboard_access": "basic",
            "priority_routing": False,
        }
    # Keep payload stable for frontend widgets.
    try:
        metrics = get_metrics()
    except Exception:
        metrics = dict(_METRICS_FALLBACK)
    return {
        "ok": True,
        "usage": usage,
        "value_generated": {
            "money_saved": float(metrics.get("money_moved", 0) or 0),
            "actions_taken": int(metrics.get("total_refunds", 0) or 0) + int(metrics.get("total_credits", 0) or 0),
        },
        "metrics": metrics,
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
    }


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
        # Anonymous extension traffic: same sliding-window pattern as workspace guest (12/min per key).
        username = "extension_guest"
        if not check_rate_limit("__ext_guest__"):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": "60"},
            )
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
# Thread-level lock for outreach_queue.json file I/O.
# IMPORTANT: This protects against intra-process concurrency only.
# If running multiple Uvicorn worker processes (gunicorn --workers N),
# migrate outreach queue persistence to the SQLite DB.
import threading as _threading

_outreach_queue_lock = _threading.Lock()
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
    with _outreach_queue_lock:
        try:
            if not os.path.exists(OUTREACH_QUEUE_PATH):
                return []
            with open(OUTREACH_QUEUE_PATH, "r", encoding="utf-8") as _f:
                data = json.load(_f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _write_outreach_queue(leads: list[dict[str, Any]]) -> None:
    tmp_path = OUTREACH_QUEUE_PATH + ".tmp"
    with _outreach_queue_lock:
        with open(tmp_path, "w", encoding="utf-8") as _f:
            json.dump(leads, _f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, OUTREACH_QUEUE_PATH)


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


# =============================================================================
# OUTCOMES — post-hoc signals (authenticated)
# =============================================================================


@app.post("/outcomes/{outcome_key}/reopen")
def mark_outcome_reopened(
    outcome_key: str,
    _user: User = Depends(require_authenticated_user),
):
    """Signal that a ticket was reopened after this outcome."""
    if not mark_ticket_reopened(outcome_key):
        raise HTTPException(status_code=404, detail="Outcome not found for this key.")
    return {"ok": True, "outcome_key": outcome_key}


@app.post("/outcomes/{outcome_key}/crm-close")
def mark_outcome_crm_closed(
    outcome_key: str,
    _user: User = Depends(require_authenticated_user),
):
    """Signal that a CRM lead was closed/won linked to this outcome."""
    if not mark_crm_closed(outcome_key):
        raise HTTPException(status_code=404, detail="Outcome not found for this key.")
    return {"ok": True, "outcome_key": outcome_key}


# =============================================================================
# METRICS — clean summary endpoint
# =============================================================================

@app.get("/metrics")
def public_metrics(
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    """
    Clean metrics summary.  Returns everything needed to show value and
    drive plan conversion: tickets handled, money moved, real outcomes,
    and current plan usage.
    """
    total_tickets = db.query(Ticket).count()
    auto_resolved = db.query(Ticket).filter(Ticket.status == "resolved").count()
    pending       = db.query(ActionLog).filter(
        ActionLog.requires_approval == 1, ActionLog.approved == 0
    ).count()
    refund_total  = float(db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "refund").scalar() or 0)
    credit_total  = float(db.query(func.sum(ActionLog.amount)).filter(ActionLog.action == "credit").scalar() or 0)

    outcome_stats = get_outcome_stats()
    usage_summary = get_usage_summary(user)
    public_tier   = get_public_plan_name(user)
    plan_cfg      = get_plan_config(public_tier)

    return {
        "tickets_handled":      total_tickets,
        "auto_resolved":        auto_resolved,
        "auto_resolution_rate": round(auto_resolved / max(1, total_tickets) * 100, 1),
        "pending_approvals":    pending,
        "money_moved":          round(refund_total + credit_total, 2),
        "refunds_issued":       round(refund_total, 2),
        "credits_issued":       round(credit_total, 2),
        "real_outcomes":        outcome_stats,
        "avg_impact_score":     float(outcome_stats.get("avg_impact_score", 0.5) or 0.5),
        "excellent_rate":       float(outcome_stats.get("excellent_rate", 0.0) or 0.0),
        "bad_rate":             float(outcome_stats.get("bad_rate", 0.0) or 0.0),
        "your_plan":            public_tier,
        "your_usage":           usage_summary["usage"],
        "your_limit":           plan_cfg["monthly_limit"],
        "your_remaining":       usage_summary["remaining"],
        "upgrade_available":    public_tier in {"free", "pro"},
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)