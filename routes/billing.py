from __future__ import annotations

import json
import logging
from urllib.parse import quote_plus

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import app as app_mod
from services import stripe_service

router = APIRouter(tags=["billing"])

logger = logging.getLogger("xalvion.api")


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
    }


@router.get("/integrations/stripe/connect")
def integrations_stripe_connect(user: app_mod.User = Depends(app_mod.require_authenticated_user)):
    if not app_mod.STRIPE_KEY or not app_mod.STRIPE_CONNECT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Stripe Connect is not configured.")

    state = app_mod.create_stripe_state(user.username)
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

    return result


@router.post("/actions/charge")
def actions_charge(
    req: app_mod.ChargeActionRequest,
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
):
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

    return result


@router.get("/billing/plans")
def billing_plans(user: app_mod.User = Depends(app_mod.get_current_user)):
    return app_mod.build_upgrade_payload(app_mod.get_public_plan_name(user))


@router.post("/billing/upgrade")
def upgrade_plan(
    req: app_mod.UpgradeRequest,
    user: app_mod.User = Depends(app_mod.require_authenticated_user),
    db: Session = Depends(app_mod.get_db),
):
    desired = (req.tier or "").strip().lower()
    current_tier = app_mod.get_public_plan_name(user)
    stripe_service.validate_upgrade_request(desired, current_tier)

    if app_mod.STRIPE_KEY and app_mod.PRICE_MAP.get(desired):
        session = stripe_service.create_checkout_session_for_user(user, desired)
        return {
            "mode": "checkout",
            "checkout_url": session.url,
            "session_id": session.id,
            "tier": current_tier,
            "usage": int(getattr(user, "usage", 0) or 0),
            "limit": app_mod.get_plan_config(current_tier)["monthly_limit"],
            "remaining": max(0, app_mod.get_plan_config(current_tier)["monthly_limit"] - int(getattr(user, "usage", 0) or 0)),
        }

    if not app_mod.ALLOW_DIRECT_BILLING_BYPASS:
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
    usage_summary = app_mod.get_usage_summary(user)
    return {
        "mode": "direct",
        "message": f"Upgraded to {desired}",
        "tier": usage_summary["tier"],
        "usage": usage_summary["usage"],
        "limit": usage_summary["limit"],
        "remaining": usage_summary["remaining"],
    }


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(app_mod.get_db)):
    if not app_mod.STRIPE_WEBHOOK_SECRET and getattr(app_mod, "ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=500, detail="Stripe webhook secret not configured")
    if not app_mod.STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = (
            stripe.Webhook.construct_event(payload, sig_header, app_mod.STRIPE_WEBHOOK_SECRET)
            if app_mod.STRIPE_WEBHOOK_SECRET
            else stripe.Event.construct_from(json.loads(payload.decode("utf-8")), stripe.api_key)
        )
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
                upgraded_user = stripe_service.apply_successful_upgrade(db, username, tier)
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
            record = db.query(app_mod.ProcessedWebhook).filter(app_mod.ProcessedWebhook.event_id == event_id).first()
            if record:
                record.outcome = outcome
                record.detail = detail
                db.commit()
        except Exception:
            pass

    return {"received": True, "type": event_type, "outcome": outcome}
