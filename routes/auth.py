from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import app as app_mod

router = APIRouter(tags=["auth"])

logger = logging.getLogger("xalvion.api")


def _tier_upgrade_unlocks(tier: str) -> str:
    t = str(tier or "free").strip().lower()
    if t == "free":
        return "500 tickets/month, full dashboard, priority routing"
    if t == "pro":
        return "5,000 tickets/month, advanced analytics, 20 team seats"
    return ""


def _me_capacity_message(tier: str, remaining: int) -> str:
    t = str(tier or "free").strip().lower()
    if t == "elite":
        return "Elite tier — full capacity"
    if t == "pro":
        return f"Pro tier — {remaining} tickets remaining"
    return f"Free tier — {remaining} tickets left this month"


def _user_billing_motion_rollups(db: Session, username: str) -> tuple[float, int]:
    """Per-user refund/credit totals for /me value_signals (additive fields only)."""
    if not username or username in {"guest", "dev_user", "extension_guest", ""}:
        return 0.0, 0
    try:
        refund_sum = db.query(func.sum(app_mod.ActionLog.amount)).filter(
            app_mod.ActionLog.username == username,
            app_mod.ActionLog.action == "refund",
        ).scalar()
        credit_sum = db.query(func.sum(app_mod.ActionLog.amount)).filter(
            app_mod.ActionLog.username == username,
            app_mod.ActionLog.action == "credit",
        ).scalar()
        actions_done = db.query(app_mod.ActionLog).filter(
            app_mod.ActionLog.username == username,
            app_mod.ActionLog.action.in_(["refund", "credit"]),
        ).count()
        money = float(refund_sum or 0) + float(credit_sum or 0)
        return money, int(actions_done)
    except Exception:
        return 0.0, 0


def _build_me_value_signals(
    user: app_mod.User,
    usage_summary: dict[str, Any],
    db: Session | None = None,
) -> dict[str, Any]:
    tier = app_mod.get_public_plan_name(user)
    tkey = str(tier or "free").strip().lower()
    rem = int(max(0, usage_summary.get("remaining", 0) or 0))
    usage = int(usage_summary.get("usage", 0) or 0)
    unlock_map = {
        "free":  "500 tickets/month, full dashboard, priority routing",
        "pro":   "5,000 tickets/month, advanced dashboard, 20 seats",
        "elite": "",
    }
    capacity_map = {
        "free":  f"Free tier — {rem} tickets left this month",
        "pro":   f"Pro tier — {rem} tickets remaining",
        "elite": "Elite tier — full capacity",
    }
    money_moved = 0.0
    total_actions = 0
    time_saved_mins = 0
    uname = str(getattr(user, "username", "") or "")
    if db is not None and uname not in {"", "guest", "dev_user"}:
        money_moved, total_actions = _user_billing_motion_rollups(db, uname)
        time_saved_mins = total_actions * 6
    else:
        try:
            metrics = app_mod.get_metrics()
            money_moved = float(metrics.get("money_moved", 0) or 0)
            total_actions = int(metrics.get("total_refunds", 0) or 0) + int(metrics.get("total_credits", 0) or 0)
            time_saved_mins = total_actions * 6
        except Exception:
            money_moved = 0.0
            total_actions = 0
            time_saved_mins = 0
    return {
        "tickets_handled":    usage,
        "upgrade_unlocks":    unlock_map.get(tkey, _tier_upgrade_unlocks(tier)),
        "capacity_message":   capacity_map.get(tkey, _me_capacity_message(tier, rem)),
        "money_moved":        round(money_moved, 2),
        "actions_taken":      total_actions,
        "time_saved_minutes": time_saved_mins,
    }


@router.get("/me")
def me(
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    usage_summary = app_mod.get_usage_summary(user)
    public_username = "" if user.username in {"guest", "dev_user"} else user.username
    public_tier = app_mod.get_public_plan_name(user)
    public_plan = app_mod.get_plan_config(public_tier)
    public_limit = int(public_plan["monthly_limit"])
    usage = int(usage_summary["usage"])
    remaining = max(0, public_limit - usage)
    if public_limit >= 10**9:
        usage_pct = 0.0
        approaching_limit = False
        at_limit = False
    else:
        usage_pct = float(usage) / float(max(1, public_limit))
        approaching_limit = usage_pct >= 0.75
        at_limit = usage >= public_limit
    return {
        "username": public_username,
        "tier": public_tier,
        "usage": usage_summary["usage"],
        "limit": public_limit,
        "remaining": remaining,
        "dashboard_access": public_plan["dashboard_access"],
        "priority_routing": public_plan["priority_routing"],
        "is_dev": usage_summary["tier"] == "dev" and user.username == app_mod.ADMIN_USERNAME,
        "is_admin": user.username == app_mod.ADMIN_USERNAME,
        "stripe_connected": bool(getattr(user, "stripe_connected", 0)),
        "stripe_account_id": getattr(user, "stripe_account_id", None),
        "usage_pct": round(usage_pct, 4),
        "approaching_limit": approaching_limit,
        "at_limit": at_limit,
        "value_signals": _build_me_value_signals(
            user,
            {**usage_summary, "remaining": remaining},
            db=db,
        ),
    }


@router.post("/signup")
def signup(req: app_mod.AuthRequest, db: Session = Depends(app_mod.get_db)):
    try:
        username = app_mod.validate_username(req.username)
        password = app_mod.validate_password(req.password)
    except HTTPException as exc:
        logger.info("signup_validation_failed detail=%s", exc.detail)
        raise

    if db.query(app_mod.User).filter(app_mod.User.username == username).first():
        logger.info("signup_duplicate_username username=%s", username)
        raise HTTPException(status_code=400, detail="Username already taken")

    try:
        password_hash = app_mod.hash_password(password)
    except Exception:
        logger.exception("signup_password_hash_failed username=%s", username)
        raise HTTPException(
            status_code=500,
            detail="Could not process password. Try a different password or contact support.",
        )

    try:
        db.add(app_mod.User(username=username, password=password_hash, usage=0, tier="free"))
        db.commit()
    except Exception:
        logger.exception("signup_db_error username=%s", username)
        raise HTTPException(status_code=500, detail="Could not create account. Try again.")

    logger.info("signup_ok username=%s", username)
    return {"message": "Account created", "tier": "free"}


@router.post("/login")
def login(req: app_mod.AuthRequest, db: Session = Depends(app_mod.get_db)):
    username = app_mod._normalize_username(req.username)
    password = (req.password or "").strip()

    if not username or not password:
        logger.info("login_rejected reason=missing_fields")
        raise HTTPException(status_code=400, detail="Username and password required")

    user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
    if not user or not app_mod.verify_password(password, user.password):
        logger.info("login_failed username=%s", username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.username == app_mod.ADMIN_USERNAME and user.tier != "elite":
        user.tier = "elite"
        db.commit()
        db.refresh(user)

    try:
        token = app_mod.create_token(user.username)
    except Exception:
        logger.exception("login_jwt_failed username=%s", username)
        raise HTTPException(status_code=500, detail="Could not issue session. Try again.")

    usage_summary = app_mod.get_usage_summary(user)
    logger.info("login_ok username=%s tier=%s", username, usage_summary.get("tier"))
    return {
        "token": token,
        "username": user.username,
        "tier": usage_summary["tier"],
        "usage": usage_summary["usage"],
        "limit": usage_summary["limit"],
        "remaining": usage_summary["remaining"],
        "is_admin": user.username == app_mod.ADMIN_USERNAME,
    }
