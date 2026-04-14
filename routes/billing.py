from __future__ import annotations

import json
import logging
import os
from urllib.parse import quote_plus

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

import app as app_mod
import governor as governor_mod
from growth_insights import append_insight, log_conversion_paid
from services import email_service, guest_preview_service, stripe_service

router = APIRouter(tags=["billing"])

logger = logging.getLogger("xalvion.api")

_stripe_webhook_prod_log_emitted = False


@router.get("/integrations/status")
def integration_status(
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
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
        "smtp_ready": bool(email_service.smtp_ready()),
    }


@router.get("/integrations/stripe/connect")
def integrations_stripe_connect(user: app_mod.User = Depends(app_mod.require_authenticated_user)):
    if not app_mod.STRIPE_KEY or not app_mod.STRIPE_CONNECT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Stripe Connect is not configured.")

    state = app_mod.create_stripe_state(user.username)
    decoded_state_user = app_mod.decode_stripe_state(state)
    if decoded_state_user != user.username:
        logger.error(
            "stripe_state_roundtrip_failed username=%s decoded=%r",
            user.username,
            decoded_state_user,
        )
        raise HTTPException(status_code=500, detail="Could not start Stripe Connect. Try again.")
    url = stripe_service.build_stripe_connect_authorize_url(
        client_id=app_mod.STRIPE_CONNECT_CLIENT_ID,
        redirect_uri=app_mod.STRIPE_CONNECT_REDIRECT_URI,
        state=state,
    )
    return {"url": url}


@router.get("/integrations/stripe/callback")
def stripe_connect_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(app_mod.get_db),
):
    if error:
        detail = error_description or error or "Stripe connection was not completed."
        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus(detail)}",
            status_code=303,
        )

    if not code or not state:
        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus('Missing Stripe callback parameters.')}",
            status_code=303,
        )

    username = app_mod.decode_stripe_state(state)
    if not username:
        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus('Invalid or expired Stripe connect state.')}",
            status_code=303,
        )

    user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
    if not user:
        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus('No account matches this Stripe session. Log in again and reconnect.')}",
            status_code=303,
        )

    try:
        token_response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=code,
        )

        user.stripe_connected = 1
        if isinstance(token_response, dict) and token_response.get("error"):
            logger.error("stripe_connect_oauth_error error=%s", str(token_response.get("error"))[:500])
            return app_mod.RedirectResponse(
                url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus('Could not complete Stripe connection. Please try again.')}",
                status_code=303,
            )

        user.stripe_account_id = token_response.get("stripe_user_id") if isinstance(token_response, dict) else None
        user.stripe_livemode = 1 if bool(token_response.get("livemode")) else 0
        scope_val = token_response.get("scope") if isinstance(token_response, dict) else None
        user.stripe_scope = str(scope_val) if scope_val else ""

        db.commit()

        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=success&detail={quote_plus('Stripe connected successfully.')}",
            status_code=303,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("stripe_connect_callback_failed")
        return app_mod.RedirectResponse(
            url=f"{app_mod.FRONTEND_URL}?stripe=error&detail={quote_plus('Could not complete Stripe connection. Please try again.')}",
            status_code=303,
        )


@router.post("/integrations/stripe/disconnect")
def integrations_stripe_disconnect(user: app_mod.User = Depends(app_mod.require_authenticated_user), db: Session = Depends(app_mod.get_db)):
    db_user = db.query(app_mod.User).filter(app_mod.User.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.stripe_connected = 0
    db_user.stripe_account_id = None
    db_user.stripe_livemode = 0
    db_user.stripe_scope = None
    db.commit()
    return {"ok": True, "stripe_connected": False}


@router.post("/actions/refund")
def actions_refund(
    req: app_mod.RefundActionRequest,
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
):
    # FIX 5: Route manual refunds through the governor before execution.
    _gov_ticket = {
        "issue_type": "manual_refund",
        "sentiment": 5,
        "abuse_score": 0,
        "plan_tier": str(getattr(user, "tier", "free") or "free"),
    }
    _gov_decision = {
        "action": "refund",
        "amount": float(req.amount or 0),
        "auto_refund_allowed": False,
        "confidence": 0.85,
    }
    _gov_memory = {
        "abuse_score": 0,
        "refund_count": 0,
        "sentiment_avg": 5,
    }
    try:
        gov_result = governor_mod.gate_execution(_gov_ticket, _gov_decision, _gov_memory)
    except Exception as _gov_exc:
        logger.error("governor_gate_failed_manual_refund detail=%s", str(_gov_exc)[:300], exc_info=True)
        gov_result = {
            "execution_mode": "review",
            "requires_approval": True,
            "governor_reason": "Governor error (soft-fail) — review required",
        }

    _gov_mode = str(gov_result.get("execution_mode", "review") or "review").strip().lower()
    if _gov_mode == "blocked":
        raise HTTPException(
            status_code=403,
            detail=str(gov_result.get("governor_reason", "Refund blocked by governor policy.")),
        )

    requires_approval = _gov_mode == "review"

    result = stripe_service.execute_real_refund(
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

    if requires_approval:
        result["requires_approval"] = True

    return result


@router.post("/actions/charge")
def actions_charge(
    req: app_mod.ChargeActionRequest,
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
):
    # Route manual charges through the governor before execution.
    _gov_ticket = {
        "issue_type": "manual_charge",
        "sentiment": 5,
        "abuse_score": 0,
        "plan_tier": str(getattr(user, "tier", "free") or "free"),
        "customer_id": str(getattr(req, "customer_id", "") or "").strip(),
        "payment_method_id": str(getattr(req, "payment_method_id", "") or "").strip(),
    }
    _gov_decision = {
        "action": "charge",
        "amount": float(getattr(req, "amount", 0) or 0),
        "confidence": 0.85,
    }
    _gov_memory = {
        "abuse_score": 0,
        "refund_count": 0,
        "sentiment_avg": 5,
    }
    try:
        gov_result = governor_mod.gate_execution(_gov_ticket, _gov_decision, _gov_memory)
    except Exception as _gov_exc:
        logger.error("governor_gate_failed_manual_charge detail=%s", str(_gov_exc)[:300], exc_info=True)
        gov_result = {
            "execution_mode": "review",
            "requires_approval": True,
            "governor_reason": "Governor error (soft-fail) — review required",
        }

    _gov_mode = str(gov_result.get("execution_mode", "review") or "review").strip().lower()
    if _gov_mode == "blocked":
        raise HTTPException(
            status_code=403,
            detail=str(gov_result.get("governor_reason", "Charge blocked by governor policy.")),
        )

    # Review means approval gating: do NOT execute Stripe charge.
    if _gov_mode == "review":
        return {
            "ok": False,
            "status": "requires_approval",
            "requires_approval": True,
            "execution_mode": "review",
            "governor_reason": str(gov_result.get("governor_reason", "Review required under governor policy") or ""),
            "governor_risk_level": str(gov_result.get("governor_risk_level", "") or ""),
            "governor_risk_score": int(gov_result.get("governor_risk_score", 0) or 0),
            "governor_factors": list(gov_result.get("governor_factors") or []),
            "approved": bool(gov_result.get("approved", False)),
            "violations": list(gov_result.get("violations") or []),
        }

    # Allowed/auto (and any unexpected non-blocked, non-review mode) proceeds to execution.
    result = stripe_service.execute_manual_charge(
        user=user,
        customer_id=req.customer_id,
        payment_method_id=req.payment_method_id,
        amount=req.amount,
        currency=req.currency,
        description=req.description,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("detail", "Charge failed.")))

    # Preserve governor fields for consistency with the refund route patterns.
    if isinstance(result, dict):
        result.setdefault("requires_approval", False)
        result.setdefault("execution_mode", _gov_mode)
        if "governor_reason" in gov_result:
            result.setdefault("governor_reason", str(gov_result.get("governor_reason") or ""))
        if "governor_risk_level" in gov_result:
            result.setdefault("governor_risk_level", str(gov_result.get("governor_risk_level") or ""))
        if "governor_risk_score" in gov_result:
            result.setdefault("governor_risk_score", int(gov_result.get("governor_risk_score", 0) or 0))
        if "governor_factors" in gov_result:
            result.setdefault("governor_factors", list(gov_result.get("governor_factors") or []))
        if "approved" in gov_result:
            result.setdefault("approved", bool(gov_result.get("approved", False)))
        if "violations" in gov_result:
            result.setdefault("violations", list(gov_result.get("violations") or []))

    return result


@router.get("/billing/plans")
def billing_plans(
    user: app_mod.User = Depends(app_mod.get_current_user),
    guest_client_id: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    payload = app_mod.build_upgrade_payload(app_mod.get_public_plan_name(user))
    if app_mod.is_session_guest(user):
        payload["guest_preview"] = guest_preview_service.guest_preview_snapshot(guest_client_id)
    return payload


@router.post("/billing/upgrade")
def upgrade_plan(
    req: app_mod.UpgradeRequest,
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
    db: Session = Depends(app_mod.get_db),
):
    # FIX 3: Billing must be configured before any upgrade attempt.
    if not app_mod.BILLING_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Billing not configured. Contact support.",
        )

    desired = (req.tier or "").strip().lower()
    current_tier = app_mod.get_public_plan_name(user)
    stripe_service.validate_upgrade_request(desired, current_tier)

    # FIX 4: ALLOW_DIRECT_BILLING_BYPASS removed — upgrade ALWAYS goes through Stripe checkout.
    if not app_mod.STRIPE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing not configured. Contact support.",
        )

    trig = (getattr(req, "upgrade_trigger", None) or "").strip()[:200]
    session = stripe_service.create_checkout_session_for_user(user, desired, upgrade_trigger=trig or None)
    append_insight(
        "upgrade_checkout_started",
        actor=str(getattr(user, "username", "") or ""),
        props={"desired": desired, "from": app_mod.get_public_plan_name(user), "trigger": trig},
    )
    return {
        "mode": "checkout",
        "checkout_url": session.url,
        "session_id": session.id,
        "tier": current_tier,
        "usage": int(getattr(user, "usage", 0) or 0),
        "limit": app_mod.get_plan_config(current_tier)["monthly_limit"],
        "remaining": max(0, app_mod.get_plan_config(current_tier)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
    }


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(app_mod.get_db)):
    stripe_key = str(app_mod.STRIPE_KEY or "").strip()
    webhook_secret = str(app_mod.STRIPE_WEBHOOK_SECRET or "").strip()
    is_live = stripe_key.startswith("sk_live_")
    env = str(getattr(app_mod, "ENVIRONMENT", "development") or "development").strip().lower()

    if not webhook_secret and (is_live or env == "production"):
        raise HTTPException(
            status_code=500,
            detail="Stripe webhook secret is required in production. Configure STRIPE_WEBHOOK_SECRET."
        )
    if not app_mod.STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        webhook_secret = str(app_mod.STRIPE_WEBHOOK_SECRET or "").strip()
        stripe_key = str(app_mod.STRIPE_KEY or "").strip()
        is_live = stripe_key.startswith("sk_live_")

        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        elif is_live:
            # Live key without webhook secret should have been caught at startup (Fix 2).
            # If we somehow reach here, refuse to process.
            raise HTTPException(
                status_code=500,
                detail="Cannot process Stripe webhook: STRIPE_WEBHOOK_SECRET is required with a live key."
            )
        else:
            # Development only — unsigned webhook accepted for local testing
            event = stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
    except stripe.error.SignatureVerificationError as exc:
        logger.warning(
            "stripe_webhook_rejected_invalid_signature env=%s detail=%s",
            env,
            str(exc)[:300],
        )
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook parse failed: {exc}") from exc

    event_type = str(getattr(event, "type", "") or "")
    event_data = getattr(event, "data", None)
    data_object = getattr(event_data, "object", None)
    event_id = str(getattr(event, "id", "") or "")

    if event_id:
        existing = db.query(app_mod.ProcessedWebhook).filter(app_mod.ProcessedWebhook.event_id == event_id).first()
        if existing:
            return {"received": True, "type": event_type, "duplicate": True}

        try:
            db.add(app_mod.ProcessedWebhook(
                event_id=event_id,
                event_type=event_type,
                processed_at=app_mod._now_iso(),
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
                tier = stripe_service.infer_tier_from_checkout_session(session_id)

            if username and tier:
                sub_raw = getattr(data_object, "subscription", None)
                sub_id = ""
                if isinstance(sub_raw, str):
                    sub_id = sub_raw.strip()
                elif sub_raw is not None:
                    sub_id = str(getattr(sub_raw, "id", "") or "").strip()
                upgraded_user = stripe_service.apply_successful_upgrade(
                    db, username, tier, stripe_subscription_id=sub_id or None
                )
                if upgraded_user:
                    utrig = ""
                    try:
                        utrig = str(metadata.get("upgrade_trigger") or "")[:200]
                    except Exception:
                        utrig = ""
                    try:
                        log_conversion_paid(username, tier, utrig or None)
                    except Exception:
                        logger.warning("growth_conversion_log_failed", exc_info=True)
                if not upgraded_user:
                    outcome = "skipped"
                    detail = f"User not found: {username!r}"
            else:
                outcome = "skipped"
                detail = "Missing username or tier in event payload"

        elif event_type == "customer.subscription.deleted":
            outcome, detail = stripe_service.apply_subscription_deleted(db, data_object)

        elif event_type == "customer.subscription.updated":
            outcome, detail = stripe_service.apply_subscription_updated(db, data_object)

    except Exception as process_exc:
        outcome = "failed"
        detail = str(process_exc)[:500]

    if event_id:
        try:
            record = db.query(app_mod.ProcessedWebhook).filter(app_mod.ProcessedWebhook.event_id == event_id).first()
            if record:
                record.outcome = outcome
                record.detail = detail
                db.commit()
        except Exception:
            pass

    return {"received": True, "type": event_type, "outcome": outcome}
