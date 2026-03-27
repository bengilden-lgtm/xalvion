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
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from agent import run_agent

try:
    from analytics import get_metrics
except Exception:
    def get_metrics():
        return {}


load_dotenv(override=True)

# =========================================================
# CONFIG
# =========================================================

SECRET_KEY = os.getenv("JWT_SECRET", "dev_secret_change_me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "120"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_ELITE = os.getenv("STRIPE_PRICE_ELITE", "").strip()
ALLOW_DIRECT_BILLING_BYPASS = os.getenv("ALLOW_DIRECT_BILLING_BYPASS", "false").strip().lower() == "true"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8001").rstrip("/")
CHECKOUT_SUCCESS_URL = os.getenv("CHECKOUT_SUCCESS_URL", f"{FRONTEND_URL}?checkout=success")
CHECKOUT_CANCEL_URL = os.getenv("CHECKOUT_CANCEL_URL", f"{FRONTEND_URL}?checkout=cancel")

STREAM_CHUNK_SIZE = 18
STREAM_CHUNK_DELAY = 0.02
STATUS_STEP_DELAY = 0.22
MAX_AUTO_REFUND = 50

# =========================================================
# APPROVAL THRESHOLDS + LIVE MODE
# =========================================================

APPROVAL_THRESHOLD = float(os.getenv("APPROVAL_THRESHOLD", "25.00"))
LIVE_MODE = os.getenv("LIVE_MODE", "false").strip().lower() == "true"

# =========================================================
# RULES SYSTEM
# =========================================================

REFUND_RULES = {
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
    "min_confidence": 0.5,
    "min_quality": 0.5,
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

PRICE_MAP = {
    "pro": STRIPE_PRICE_PRO,
    "elite": STRIPE_PRICE_ELITE,
}

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

# =========================================================
# APP + STATIC
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
APP_JS_PATH = os.path.join(BASE_DIR, "app.js")
LANDING_PATH = os.path.join(BASE_DIR, "landing.html")
FLUID_DIR = os.path.join(BASE_DIR, "fluid")

app = FastAPI(title="Xalvion Sovereign Brain")

if os.path.isdir(FLUID_DIR):
    app.mount("/fluid", StaticFiles(directory=FLUID_DIR), name="fluid")

ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "https://www.xalvion.tech",
    "https://xalvion.tech",
]

frontend_origin = os.getenv("FRONTEND_URL", "").rstrip("/")
if frontend_origin and frontend_origin not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(frontend_origin)

extra_origins = os.getenv("ALLOWED_ORIGINS", "")
for origin in [item.strip().rstrip("/") for item in extra_origins.split(",") if item.strip()]:
    if origin not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aurum.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
request_log: dict[str, list[float]] = {}


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    usage = Column(Integer, default=0)
    tier = Column(String, default="free")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    username = Column(String, nullable=False, index=True)
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


Base.metadata.create_all(bind=engine)

# =========================================================
# SCHEMAS
# =========================================================


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


class UpgradeRequest(BaseModel):
    tier: str


class AdminUserAction(BaseModel):
    username: str


# =========================================================
# HELPERS
# =========================================================


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password = password_bytes[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_plan_name(user: User | None) -> str:
    if not user:
        return "free"
    tier = (getattr(user, "tier", None) or "free").strip().lower()
    return tier if tier in PLAN_CONFIG else "free"


def get_public_plan_name(user: User | None) -> str:
    tier = get_plan_name(user)
    return tier if tier in PUBLIC_PLAN_TIERS else "free"


def get_plan_config(tier: str | None) -> dict[str, Any]:
    key = (tier or "free").strip().lower()
    return PLAN_CONFIG.get(key, PLAN_CONFIG["free"])


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


def check_rate_limit(user_id: str) -> bool:
    now = time.time()
    request_log.setdefault(user_id, [])
    request_log[user_id] = [t for t in request_log[user_id] if now - t < 60]
    if len(request_log[user_id]) >= 12:
        return False
    request_log[user_id].append(now)
    return True


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
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
        raise HTTPException(status_code=401, detail="User not found")

    return user


def require_authenticated_user(user: User = Depends(get_current_user)):
    if getattr(user, "username", "") in {"", "guest"}:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: User = Depends(get_current_user)):
    if user.username != ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def enforce_plan_limits(user: User) -> None:
    plan_name = get_plan_name(user)
    plan = get_plan_config(plan_name)

    if not check_rate_limit(user.username):
        raise HTTPException(status_code=429, detail="Too many requests")

    usage = int(getattr(user, "usage", 0) or 0)
    limit = int(plan["monthly_limit"])

    if usage >= limit:
        detail = (
            f"{plan['label']} plan limit reached. "
            f"You have used {usage}/{limit} tickets. Upgrade to continue using Xalvion."
        )
        raise HTTPException(
            status_code=402,
            detail=detail,
            headers={
                "X-Xalvion-Plan": plan_name,
                "X-Xalvion-Limit": str(limit),
            },
        )


def build_agent_meta(req: SupportRequest, user: User) -> dict[str, Any]:
    plan_name = get_plan_name(user)
    return {
        "sentiment": req.sentiment if req.sentiment is not None else 5,
        "ltv": req.ltv if req.ltv is not None else 0,
        "order_status": req.order_status if req.order_status is not None else "unknown",
        "plan_tier": plan_name,
        "priority_routing": get_plan_config(plan_name)["priority_routing"],
        "payment_intent_id": (req.payment_intent_id or "").strip(),
        "charge_id": (req.charge_id or "").strip(),
    }


def safe_refund_reason(value: str | None) -> str:
    text = (value or "").strip().lower()
    allowed = {
        "duplicate",
        "fraudulent",
        "requested_by_customer",
    }
    return text if text in allowed else "requested_by_customer"


def cents_from_dollars(amount: Any) -> int:
    try:
        value = float(amount)
    except Exception:
        value = 0.0

    if value <= 0:
        return 0

    if value > MAX_AUTO_REFUND:
        value = float(MAX_AUTO_REFUND)

    return int(round(value * 100))


def dollars_from_cents(cents: int) -> float:
    return int(cents) / 100


def rewrite_refund_failure_message(reason: str) -> str:
    return (
        "I’ve opened this for manual review because I couldn’t complete the refund automatically. "
        f"{reason}"
    ).strip()


def get_charge_context(
    *,
    payment_intent_id: str | None,
    charge_id: str | None,
) -> dict[str, Any]:
    payment_intent_id = (payment_intent_id or "").strip()
    charge_id = (charge_id or "").strip()

    if payment_intent_id:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        charges = (payment_intent.get("charges") or {}).get("data") or []
        if not charges:
            raise Exception("No charge found for this payment_intent.")
        charge = charges[0]
        return {
            "payment_intent_id": payment_intent_id,
            "charge_id": charge.get("id", ""),
            "charge_amount": int(charge.get("amount", 0) or 0),
            "currency": str(charge.get("currency", "usd") or "usd").upper(),
            "captured": bool(charge.get("captured", True)),
            "refunded": bool(charge.get("refunded", False)),
            "amount_refunded": int(charge.get("amount_refunded", 0) or 0),
        }

    if charge_id:
        charge = stripe.Charge.retrieve(charge_id)
        return {
            "payment_intent_id": str(charge.get("payment_intent", "") or ""),
            "charge_id": charge_id,
            "charge_amount": int(charge.get("amount", 0) or 0),
            "currency": str(charge.get("currency", "usd") or "usd").upper(),
            "captured": bool(charge.get("captured", True)),
            "refunded": bool(charge.get("refunded", False)),
            "amount_refunded": int(charge.get("amount_refunded", 0) or 0),
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
    tier = get_plan_name(user)
    issue_type = str(result.get("issue_type", "general_support") or "general_support").strip().lower()
    order_status = str(result.get("order_status", "unknown") or "unknown").strip().lower()
    confidence = float(result.get("confidence", 0) or 0)
    quality = float(result.get("quality", 0) or 0)

    rule_checks: list[dict[str, Any]] = []

    def add_rule(name: str, passed: bool, detail: str) -> None:
        rule_checks.append({
            "rule": name,
            "passed": passed,
            "detail": detail,
        })

    add_rule(
        "refund_rules_enabled",
        REFUND_RULES["enabled"],
        "Automatic refund rules are enabled." if REFUND_RULES["enabled"] else "Automatic refund rules are disabled."
    )
    add_rule(
        "allowed_tier",
        tier in REFUND_RULES["allowed_tiers"],
        f"Tier '{tier}' is {'allowed' if tier in REFUND_RULES['allowed_tiers'] else 'not allowed'} for automatic refunds."
    )
    add_rule(
        "allowed_issue_type",
        issue_type in REFUND_RULES["allowed_issue_types"],
        f"Issue type '{issue_type}' is {'allowed' if issue_type in REFUND_RULES['allowed_issue_types'] else 'not allowed'} for automatic refunds."
    )
    add_rule(
        "not_blocked_order_status",
        order_status not in REFUND_RULES["blocked_order_statuses"],
        f"Order status '{order_status}' is {'acceptable' if order_status not in REFUND_RULES['blocked_order_statuses'] else 'blocked'} for automatic refunds."
    )
    add_rule(
        "minimum_confidence",
        confidence >= REFUND_RULES["min_confidence"],
        f"Confidence {confidence:.2f} must be at least {REFUND_RULES['min_confidence']:.2f}."
    )
    add_rule(
        "minimum_quality",
        quality >= REFUND_RULES["min_quality"],
        f"Quality {quality:.2f} must be at least {REFUND_RULES['min_quality']:.2f}."
    )

    charge_amount = int(charge_context["charge_amount"])
    amount_refunded = int(charge_context.get("amount_refunded", 0) or 0)
    remaining_refundable = max(0, charge_amount - amount_refunded)

    add_rule(
        "captured_charge",
        bool(charge_context.get("captured", False)),
        "Charge is captured and can be refunded." if charge_context.get("captured", False) else "Charge is not captured."
    )
    add_rule(
        "remaining_refundable_amount",
        remaining_refundable > 0,
        f"Remaining refundable amount is ${dollars_from_cents(remaining_refundable):.2f}."
    )
    add_rule(
        "auto_refund_threshold",
        dollars_from_cents(refund_cents) <= REFUND_RULES["max_auto_refund_amount"],
        f"Refund ${dollars_from_cents(refund_cents):.2f} must be at or below ${REFUND_RULES['max_auto_refund_amount']:.2f}."
    )
    add_rule(
        "positive_requested_amount",
        requested_cents > 0,
        f"Requested refund is ${dollars_from_cents(requested_cents):.2f}."
    )
    add_rule(
        "positive_refund_amount",
        refund_cents > 0,
        f"Actual refund would be ${dollars_from_cents(refund_cents):.2f}."
    )

    blocked_rules = [r for r in rule_checks if not r["passed"]]
    allowed = len(blocked_rules) == 0

    return {
        "allowed": allowed,
        "blocked_rules": blocked_rules,
        "all_rules": rule_checks,
        "tier": tier,
        "issue_type": issue_type,
        "order_status": order_status,
        "confidence": confidence,
        "quality": quality,
        "requested_amount": dollars_from_cents(requested_cents),
        "charge_amount": dollars_from_cents(charge_amount),
        "remaining_refundable_amount": dollars_from_cents(remaining_refundable),
        "refund_amount": dollars_from_cents(refund_cents),
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
    payment_intent_id = (payment_intent_id or "").strip()
    charge_id = (charge_id or "").strip()

    if not STRIPE_KEY:
        return {"ok": False, "status": "stripe_not_configured", "detail": "Automatic refunds are not configured yet."}

    if not payment_intent_id and not charge_id:
        return {
            "ok": False,
            "status": "missing_payment_reference",
            "detail": "A payment_intent_id or charge_id is required for an automatic refund.",
        }

    cents_requested = cents_from_dollars(amount)
    if cents_requested <= 0:
        return {"ok": False, "status": "invalid_refund_amount", "detail": "Refund amount must be greater than zero."}

    try:
        charge_context = get_charge_context(payment_intent_id=payment_intent_id, charge_id=charge_id)
        charge_amount = int(charge_context["charge_amount"])
        amount_refunded = int(charge_context.get("amount_refunded", 0) or 0)
        remaining_refundable = max(0, charge_amount - amount_refunded)

        if remaining_refundable <= 0:
            return {
                "ok": False,
                "status": "no_refundable_balance",
                "detail": "This charge has no refundable balance remaining.",
                "charge_context": charge_context,
            }

        refund_cents = min(cents_requested, remaining_refundable)

        rules_summary = evaluate_refund_rules(
            result=result,
            user=user,
            charge_context=charge_context,
            requested_cents=cents_requested,
            refund_cents=refund_cents,
        )

        if not rules_summary["allowed"]:
            blocked_details = "; ".join(rule["detail"] for rule in rules_summary["blocked_rules"])
            return {
                "ok": False,
                "status": "refund_blocked_by_rules",
                "detail": blocked_details or "Refund blocked by system rules.",
                "rules_summary": rules_summary,
                "charge_context": charge_context,
            }

        payload: dict[str, Any] = {
            "amount": refund_cents,
            "reason": safe_refund_reason(refund_reason),
            "metadata": {
                "source": "xalvion",
                "username": username,
                "issue_type": issue_type,
                "requested_refund_cents": str(cents_requested),
                "charge_amount_cents": str(charge_amount),
                "remaining_refundable_cents": str(remaining_refundable),
                "rule_tier": rules_summary["tier"],
            },
        }

        if payment_intent_id:
            payload["payment_intent"] = payment_intent_id
        else:
            payload["charge"] = charge_id

        refund = stripe.Refund.create(**payload)
        refund_amount = int(getattr(refund, "amount", refund_cents) or refund_cents) / 100

        return {
            "ok": True,
            "status": "refunded",
            "refund_id": getattr(refund, "id", ""),
            "amount": refund_amount,
            "currency": charge_context["currency"],
            "payment_intent_id": charge_context["payment_intent_id"] or payment_intent_id,
            "charge_id": charge_context["charge_id"] or charge_id,
            "requested_amount": cents_requested / 100,
            "charge_amount": charge_amount / 100,
            "remaining_refundable_amount": remaining_refundable / 100,
            "capped": refund_cents < cents_requested,
            "rules_summary": rules_summary,
            "charge_context": charge_context,
        }
    except Exception as exc:
        return {"ok": False, "status": "stripe_refund_failed", "detail": str(exc)}


def apply_real_actions(result: dict[str, Any], req: SupportRequest, user: User) -> dict[str, Any]:
    result = dict(result or {})
    action = str(result.get("action", "none") or "none").lower()
    issue_type = str(result.get("issue_type", "general_support") or "general_support")

    if action != "refund":
        return result

    refund_result = execute_real_refund(
        amount=int(result.get("amount", 0) or 0),
        payment_intent_id=req.payment_intent_id,
        charge_id=req.charge_id,
        refund_reason=req.refund_reason,
        username=str(getattr(user, "username", "unknown") or "unknown"),
        issue_type=issue_type,
        user=user,
        result=result,
    )

    if refund_result.get("ok"):
        refunded_amount = refund_result.get("amount", result.get("amount", 0))
        requested_amount = refund_result.get("requested_amount", refunded_amount)
        capped = bool(refund_result.get("capped", False))

        result["action"] = "refund"
        result["amount"] = refunded_amount
        result["reason"] = (
            f"Refund capped to actual refundable amount (${refunded_amount:.2f})"
            if capped
            else "Refund processed through Stripe"
        )
        result["tool_status"] = "refunded"
        result["tool_result"] = refund_result
        result["impact"] = {"type": "refund", "amount": refunded_amount}

        if capped:
            result["response"] = (
                f"I’ve processed the refund. The original request was for ${requested_amount:.2f}, "
                f"but the refundable amount was ${refunded_amount:.2f}, so I refunded the full available balance."
            )
            result["final"] = result["response"]

        return result

    failure_detail = str(refund_result.get("detail", "Automatic refund failed.")).strip()
    result["action"] = "review"
    result["amount"] = 0
    result["reason"] = failure_detail
    result["tool_status"] = refund_result.get("status", "refund_failed")
    result["tool_result"] = refund_result
    result["impact"] = {"type": "saved", "amount": 0}
    result["response"] = rewrite_refund_failure_message(failure_detail)
    result["final"] = result["response"]
    return result


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
        "tier": usage_summary["tier"],
        "plan_limit": usage_summary["limit"],
        "usage": usage_summary["usage"],
        "remaining": max(0, get_plan_config(get_public_plan_name(user))["monthly_limit"] - usage_summary["usage"]),
    }


def log_action(
    db: Session,
    *,
    username: str,
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
        timestamp=datetime.utcnow().isoformat(),
        username=username,
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


def check_requires_approval(action: str, amount: float) -> bool:
    if not LIVE_MODE:
        return False
    if action == "refund" and float(amount or 0) > APPROVAL_THRESHOLD:
        return True
    return False


def run_support(req: SupportRequest, user: User, db: Session) -> dict[str, Any]:
    enforce_plan_limits(user)

    result = run_agent(
        req.message,
        user_id=user.username,
        meta=build_agent_meta(req, user),
    )

    action = str(result.get("action", "none") or "none").lower()
    amount = float(result.get("amount", 0) or 0)
    needs_approval = check_requires_approval(action, amount)

    if needs_approval:
        result["action"] = "review"
        result["amount"] = 0
        result["reason"] = f"Refund of ${amount:.2f} exceeds approval threshold (${APPROVAL_THRESHOLD:.2f}). Manual approval required."
        result["response"] = "I've flagged this refund for manual approval as the amount exceeds the auto-approval limit. Your team will review and process it shortly."
        result["final"] = result["response"]
        result["tool_status"] = "pending_approval"
    else:
        result = apply_real_actions(result, req, user)

    log_action(
        db,
        username=str(getattr(user, "username", "unknown")),
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

    return serialize_support_result(result, user)


def sse_event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chunk_text(text: str, size: int = STREAM_CHUNK_SIZE) -> list[str]:
    text = text or ""
    if not text:
        return [""]
    return [text[i:i + size] for i in range(0, len(text), size)]


def build_status_sequence(result: dict[str, Any]) -> list[dict[str, str]]:
    sequence = [
        {"stage": "reviewing", "label": "Reviewing request"},
        {"stage": "routing", "label": "Choosing next step"},
    ]

    action = str(result.get("action", "none") or "none")
    action_labels = {
        "refund": "Confirming refund",
        "credit": "Applying credit",
        "review": "Review in progress",
    }

    if action in action_labels:
        sequence.append({"stage": "acting", "label": action_labels[action]})
    else:
        sequence.append({"stage": "responding", "label": "Drafting reply"})

    return sequence


def stream_support_events(result: dict[str, Any]) -> AsyncIterator[str]:
    async def generator() -> AsyncIterator[str]:
        for item in build_status_sequence(result):
            yield sse_event("status", item)
            await asyncio.sleep(STATUS_STEP_DELAY)

        for part in chunk_text(result.get("reply", ""), STREAM_CHUNK_SIZE):
            yield sse_event("chunk", {"chunk": part})
            await asyncio.sleep(STREAM_CHUNK_DELAY)

        yield sse_event(
            "meta",
            {
                "mode": result.get("mode", "unknown"),
                "quality": result.get("quality", 0),
                "confidence": result.get("confidence", 0),
                "action": result.get("action", "none"),
                "amount": result.get("amount", 0),
                "reason": result.get("reason", ""),
                "issue_type": result.get("issue_type", "general_support"),
                "order_status": result.get("order_status", "unknown"),
                "tool_status": result.get("tool_status", "unknown"),
                "tool_result": result.get("tool_result", {}),
                "impact": result.get("impact", {}),
                "tier": result.get("tier", "free"),
                "plan_limit": result.get("plan_limit", 0),
                "usage": result.get("usage", 0),
                "remaining": result.get("remaining", 0),
            },
        )
        yield sse_event("done", {"ok": True})

    return generator()


def validate_upgrade_request(desired: str, current_tier: str) -> None:
    if desired not in {"pro", "elite"}:
        raise HTTPException(status_code=400, detail="Invalid tier")

    normalized_current = current_tier if current_tier in PUBLIC_PLAN_TIERS else "free"

    if normalized_current == desired:
        raise HTTPException(status_code=400, detail=f"Already on {desired}")

    if normalized_current == "elite" and desired == "pro":
        raise HTTPException(status_code=400, detail="Downgrades are not supported from this endpoint")


def create_checkout_session_for_user(user: User, desired: str):
    if not STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    price_id = PRICE_MAP.get(desired, "")
    if not price_id:
        raise HTTPException(status_code=500, detail=f"No Stripe price configured for {desired}")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            metadata={
                "username": user.username,
                "tier": desired,
            },
            subscription_data={
                "metadata": {
                    "username": user.username,
                    "tier": desired,
                }
            },
            client_reference_id=user.username,
        )
        print(
            f"[STRIPE] checkout session created "
            f"session_id={getattr(session, 'id', None)!r} "
            f"username={user.username!r} "
            f"desired={desired!r} "
            f"price_id={price_id!r}"
        )
    except Exception as exc:
        print(f"[STRIPE] checkout session create failed username={user.username!r} desired={desired!r} error={exc}")
        raise HTTPException(status_code=500, detail=f"Stripe checkout error: {exc}") from exc

    return session


def apply_successful_upgrade(db: Session, username: str, tier: str) -> User | None:
    print(f"[STRIPE] apply_successful_upgrade called username={username!r} tier={tier!r}")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"[STRIPE] user not found for username={username!r}")
        return None

    desired = (tier or "").strip().lower()
    if desired not in {"pro", "elite"}:
        print(f"[STRIPE] invalid desired tier={desired!r} for username={username!r}")
        return user

    print(f"[STRIPE] before upgrade user={user.username!r} current_tier={user.tier!r}")
    user.tier = desired
    db.commit()
    db.refresh(user)
    print(f"[STRIPE] upgrade committed for user={user.username!r}, new tier={user.tier!r}")
    return user


def infer_tier_from_checkout_session(session_id: str) -> str:
    if not session_id or not STRIPE_KEY:
        return ""

    try:
        line_items = stripe.checkout.Session.list_line_items(session_id, limit=10)
    except Exception as exc:
        print(f"[STRIPE] line item lookup failed session_id={session_id!r} error={exc}")
        return ""

    items = getattr(line_items, "data", None) or []
    for item in items:
        price_obj = getattr(item, "price", None)
        price_id = getattr(price_obj, "id", None) or ""

        print(f"[STRIPE] line item price_id={price_id!r} for session_id={session_id!r}")

        if price_id and price_id == STRIPE_PRICE_PRO:
            return "pro"
        if price_id and price_id == STRIPE_PRICE_ELITE:
            return "elite"

    return ""


# =========================================================
# ROUTES
# =========================================================


@app.get("/")
def serve_index():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return JSONResponse({"status": "ok", "service": "xalvion-sovereign-brain", "warning": "index.html not found"})


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "xalvion-sovereign-brain"}


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    usage_summary = get_usage_summary(user)
    public_username = "" if user.username in {"guest", "dev_user"} else user.username
    public_tier = get_public_plan_name(user)
    public_plan = get_plan_config(public_tier)
    public_limit = int(public_plan["monthly_limit"])
    public_remaining = max(0, public_limit - usage_summary["usage"])

    return {
        "username": public_username,
        "tier": public_tier,
        "usage": usage_summary["usage"],
        "limit": public_limit,
        "remaining": public_remaining,
        "dashboard_access": public_plan["dashboard_access"],
        "priority_routing": public_plan["priority_routing"],
        "is_dev": usage_summary["tier"] == "dev" and user.username == ADMIN_USERNAME,
        "is_admin": user.username == ADMIN_USERNAME,
    }


@app.get("/billing/plans")
def billing_plans(user: User = Depends(get_current_user)):
    current_tier = get_public_plan_name(user)
    return build_upgrade_payload(current_tier)


@app.get("/dashboard/summary")
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    metrics = get_metrics() or {}
    total_users = db.query(User).count()
    pro_users = db.query(User).filter(User.tier == "pro").count()
    elite_users = db.query(User).filter(User.tier == "elite").count()

    usage_summary = get_usage_summary(user)

    return {
        "total_interactions": metrics.get("total_interactions", 0),
        "avg_confidence": metrics.get("avg_confidence", 0),
        "avg_quality": metrics.get("avg_quality", 0),
        "total_users": total_users,
        "pro_users": pro_users,
        "elite_users": elite_users,
        "your_usage": usage_summary["usage"],
        "your_tier": get_public_plan_name(user),
        "your_limit": get_plan_config(get_public_plan_name(user))["monthly_limit"],
        "remaining": usage_summary["remaining"],
        "dashboard_access": get_plan_config(get_public_plan_name(user))["dashboard_access"],
        "priority_routing": get_plan_config(get_public_plan_name(user))["priority_routing"],
    }


@app.post("/signup")
def signup(req: AuthRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    password = (req.password or "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User exists")

    user = User(username=username, password=hash_password(password), usage=0, tier="free")
    db.add(user)
    db.commit()

    return {"message": "User created", "tier": "free"}


@app.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.username == ADMIN_USERNAME and user.tier != "elite":
        user.tier = "elite"
        db.commit()
        db.refresh(user)

    token = create_token(user.username)
    usage_summary = get_usage_summary(user)

    return {
        "token": token,
        "tier": usage_summary["tier"],
        "usage": usage_summary["usage"],
        "limit": usage_summary["limit"],
        "remaining": usage_summary["remaining"],
        "is_admin": user.username == ADMIN_USERNAME,
    }


@app.post("/billing/upgrade")
def upgrade_plan(
    req: UpgradeRequest,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    desired = (req.tier or "").strip().lower()
    current_tier = get_public_plan_name(user)

    print(
        f"[STRIPE] /billing/upgrade called "
        f"username={getattr(user, 'username', None)!r} "
        f"current_tier={current_tier!r} "
        f"desired={desired!r}"
    )

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
            detail="Stripe is not fully configured yet. Add STRIPE_SECRET_KEY and price IDs, or enable ALLOW_DIRECT_BILLING_BYPASS for local testing.",
        )

    print(f"[STRIPE] direct billing bypass active for username={user.username!r} desired={desired!r}")

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
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    print(f"[STRIPE] webhook received payload_bytes={len(payload)} has_signature={bool(sig_header)}")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
    except Exception as exc:
        print(f"[STRIPE] webhook parse failed error={exc}")
        raise HTTPException(status_code=400, detail=f"Webhook parse failed: {exc}") from exc

    event_type = getattr(event, "type", "") or ""
    event_data = getattr(event, "data", None)
    data_object = getattr(event_data, "object", None)

    print(f"[STRIPE] webhook parsed event_type={event_type!r}")

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
            print(f"[STRIPE] inferred tier from line items tier={tier!r}")

        print(f"[STRIPE] checkout.session.completed username={username!r} tier={tier!r}")
        print(f"[STRIPE] metadata={metadata!r}")
        print(f"[STRIPE] client_reference_id={client_reference_id!r}")
        print(f"[STRIPE] session_id={session_id!r}")

        if username and tier:
            upgraded_user = apply_successful_upgrade(db, username, tier)
            print(f"[STRIPE] upgraded_user={getattr(upgraded_user, 'username', None)!r}")
        else:
            print("[STRIPE] missing username or tier in checkout.session.completed")

    if event_type in {"customer.subscription.deleted", "customer.subscription.updated"}:
        print(f"[STRIPE] subscription lifecycle event received type={event_type!r}")

    return {"received": True, "type": event_type}


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
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return [{"username": u.username, "tier": u.tier, "usage": u.usage} for u in db.query(User).all()]


@app.post("/admin/set-tier")
def admin_set_tier(
    req: AdminUserAction,
    tier: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.username == req.username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if tier not in {"free", "pro", "elite"}:
        raise HTTPException(status_code=400, detail="Invalid tier")
    target.tier = tier
    db.commit()
    return {"message": f"{req.username} set to {tier}"}


@app.get("/admin/action-logs")
def admin_action_logs(
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    logs = db.query(ActionLog).order_by(ActionLog.id.desc()).limit(max(1, min(limit, 500))).all()
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp,
            "username": log.username,
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
    ]


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
    log.approved = 1
    log.status = "approved"
    db.commit()
    return {"message": f"Action {log_id} approved", "id": log_id}


@app.post("/support")
def support(req: SupportRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)