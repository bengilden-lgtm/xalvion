from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import urlencode

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

import app as _app

logger = logging.getLogger("xalvion.stripe")


def safe_refund_reason(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text if text in {"duplicate", "fraudulent", "requested_by_customer"} else "requested_by_customer"


def cents_from_dollars(amount: Any, *, max_dollars: float | None = None) -> int:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    # Defensive: reject NaN/inf without raising. This is a no-op for normal numeric inputs.
    if not math.isfinite(value):
        value = 0.0
    cap = float(max_dollars) if max_dollars is not None else float(_app.MAX_AUTO_REFUND)
    cap = max(0.0, cap)
    return int(round(min(max(value, 0), cap) * 100))


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
    user: Any,
    charge_context: dict[str, Any],
    requested_cents: int,
    refund_cents: int,
) -> dict[str, Any]:
    from governor import normalize_plan_tier, plan_limits

    tier = _app.get_plan_name(user)
    tier_norm = normalize_plan_tier(tier)
    pl = plan_limits(tier_norm)
    cap_dollars = float(pl.get("max_refund") or 0)
    issue_type = str(result.get("issue_type", "general_support") or "general_support").strip().lower()
    order_status = str(result.get("order_status", "unknown") or "unknown").strip().lower()
    confidence = float(result.get("confidence", 0) or 0)
    quality = float(result.get("quality", 0) or 0)

    checks: list[dict[str, Any]] = []

    def _rule(name: str, passed: bool, detail: str) -> None:
        checks.append({"rule": name, "passed": passed, "detail": detail})

    rr = _app.REFUND_RULES
    _rule("enabled", rr["enabled"], "Auto refunds enabled" if rr["enabled"] else "Auto refunds disabled")
    _rule("allowed_tier", tier in rr["allowed_tiers"], f"Tier '{tier}' {'allowed' if tier in rr['allowed_tiers'] else 'not allowed'}")
    _rule("allowed_issue_type", issue_type in rr["allowed_issue_types"], f"Issue type '{issue_type}' {'allowed' if issue_type in rr['allowed_issue_types'] else 'not allowed'}")
    _rule("order_status_ok", order_status not in rr["blocked_order_statuses"], f"Order status '{order_status}' acceptable")
    _rule("min_confidence", confidence >= rr["min_confidence"], f"Confidence {confidence:.2f} >= {rr['min_confidence']:.2f}")
    _rule("min_quality", quality >= rr["min_quality"], f"Quality {quality:.2f} >= {rr['min_quality']:.2f}")

    charge_amount = int(charge_context["charge_amount"])
    amount_refunded = int(charge_context.get("amount_refunded", 0) or 0)
    remaining = max(0, charge_amount - amount_refunded)

    _rule("captured", bool(charge_context.get("captured", False)), "Charge is captured")
    _rule("has_refundable", remaining > 0, f"Remaining refundable: ${dollars_from_cents(remaining):.2f}")
    _rule(
        "within_cap",
        dollars_from_cents(refund_cents) <= cap_dollars,
        f"${dollars_from_cents(refund_cents):.2f} <= tier cap ${cap_dollars:.2f}",
    )
    _rule(
        "tier_allows_auto_refund",
        bool(pl.get("can_auto_refund")),
        "Tier allows automatic refunds" if bool(pl.get("can_auto_refund")) else "Tier does not allow automatic refunds",
    )
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
    user: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    pi = (payment_intent_id or "").strip()
    cid = (charge_id or "").strip()

    if not _app.STRIPE_KEY:
        return {"ok": False, "status": "stripe_not_configured", "detail": "Stripe not configured."}
    if not pi and not cid:
        return {"ok": False, "status": "missing_payment_reference", "detail": "payment_intent_id or charge_id required."}

    from governor import normalize_plan_tier, plan_limits

    pl = plan_limits(normalize_plan_tier(_app.get_plan_name(user)))
    max_ref_d = float(pl.get("max_refund") or _app.MAX_AUTO_REFUND)
    cents_requested = cents_from_dollars(amount, max_dollars=max_ref_d)
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


def require_connected_stripe_account(user: Any) -> str:
    if not _app.STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured.")
    stripe_account_id = str(getattr(user, "stripe_account_id", "") or "").strip()
    if stripe_account_id:
        # Safety footgun: older rows or manual DB edits can create mismatches between
        # `stripe_connected` and `stripe_account_id`. Preserve behavior (allow account_id
        # to proceed) but emit a warning so the inconsistency is detectable.
        if not bool(getattr(user, "stripe_connected", 0)):
            logger.warning(
                "stripe_connected_flag_mismatch user=%s stripe_account_id_present=1",
                str(getattr(user, "username", "") or ""),
            )
        return stripe_account_id
    raise HTTPException(status_code=400, detail="Missing connected Stripe account.")


def execute_manual_charge(
    *,
    user: Any,
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


def build_stripe_connect_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "read_write",
) -> str:
    """
    Stripe Connect OAuth URL (Standard). Single place for query shaping so
    billing routes and docs stay aligned.
    """
    qs = urlencode(
        {
            "response_type": "code",
            "client_id": (client_id or "").strip(),
            "scope": (scope or "read_write").strip(),
            "state": state or "",
            "redirect_uri": redirect_uri or "",
        }
    )
    return f"https://connect.stripe.com/oauth/authorize?{qs}"


def validate_upgrade_request(desired: str, current_tier: str) -> None:
    if desired not in {"pro", "elite"}:
        raise HTTPException(status_code=400, detail="Invalid tier")
    normalized_current = current_tier if current_tier in _app.PUBLIC_PLAN_TIERS else "free"
    if normalized_current == desired:
        raise HTTPException(status_code=400, detail=f"Already on {desired}")
    if normalized_current == "elite" and desired == "pro":
        raise HTTPException(status_code=400, detail="Downgrades not supported")


def create_checkout_session_for_user(user: Any, desired: str, upgrade_trigger: str | None = None) -> Any:
    if not _app.STRIPE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    price_id = _app.PRICE_MAP.get(desired, "")
    if not price_id:
        raise HTTPException(status_code=500, detail=f"No Stripe price configured for {desired}")

    trig = (upgrade_trigger or "").strip()[:200]
    meta = {"username": user.username, "tier": desired}
    if trig:
        meta["upgrade_trigger"] = trig

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=_app.CHECKOUT_SUCCESS_URL,
            cancel_url=_app.CHECKOUT_CANCEL_URL,
            metadata=meta,
            subscription_data={"metadata": {"username": user.username, "tier": desired}},
            client_reference_id=user.username,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stripe checkout error: {exc}") from exc

    return session


def apply_successful_upgrade(
    db: Session,
    username: str,
    tier: str,
    *,
    stripe_subscription_id: str | None = None,
    tier_source: str = "webhook",
) -> dict[str, Any]:
    user = (
        db.query(_app.User)
        .filter(_app.User.username == username)
        .with_for_update()
        .first()
    )
    if not user:
        return {"ok": False, "result": "user_not_found", "user": None}

    desired = (tier or "").strip().lower()
    if desired not in {"pro", "elite"}:
        return {"ok": True, "result": "already_on_tier", "user": user}

    if str(getattr(user, "tier", "") or "").strip().lower() == desired:
        return {"ok": True, "result": "already_on_tier", "user": user}

    user.tier = desired
    if hasattr(user, "stripe_subscription_status"):
        user.stripe_subscription_status = "active"
    if hasattr(user, "stripe_tier_source"):
        user.stripe_tier_source = (tier_source or "webhook")[:16]

    sid = (stripe_subscription_id or "").strip()
    if sid and hasattr(user, "stripe_subscription_id"):
        user.stripe_subscription_id = sid[:128]

    db.commit()
    db.refresh(user)
    return {"ok": True, "result": "upgraded", "user": user}


def infer_tier_from_checkout_session(session_id: str) -> str:
    if not session_id or not _app.STRIPE_KEY:
        return ""

    try:
        items = stripe.checkout.Session.list_line_items(session_id, limit=10)
        for item in (getattr(items, "data", None) or []):
            price_id = getattr(getattr(item, "price", None), "id", None) or ""
            if price_id == _app.STRIPE_PRICE_PRO:
                return "pro"
            if price_id == _app.STRIPE_PRICE_ELITE:
                return "elite"
    except Exception:
        return ""

    return ""


def _metadata_from_stripe_object(meta: Any) -> dict[str, str]:
    if not meta:
        return {}
    if isinstance(meta, dict):
        return {str(k): str(v) if v is not None else "" for k, v in meta.items()}
    try:
        raw = dict(meta)
        if isinstance(raw, dict):
            return {str(k): str(v) if v is not None else "" for k, v in raw.items()}
    except Exception:
        pass
    return {}


def _subscription_field(subscription: Any, key: str, default: Any = None) -> Any:
    """Read subscription fields from StripeObject or plain dict (webhook JSON)."""
    if subscription is None:
        return default
    if isinstance(subscription, dict):
        return subscription.get(key, default)
    return getattr(subscription, key, default)


def subscription_username(subscription: Any) -> str:
    meta = _metadata_from_stripe_object(_subscription_field(subscription, "metadata"))
    return (meta.get("username") or "").strip()


def _tier_for_price_id(price_id: str) -> str:
    pid = (price_id or "").strip()
    pro = (_app.STRIPE_PRICE_PRO or "").strip()
    elite = (_app.STRIPE_PRICE_ELITE or "").strip()
    if pid and pro and pid == pro:
        return "pro"
    if pid and elite and pid == elite:
        return "elite"
    return ""


def infer_tier_from_subscription(subscription: Any) -> str:
    """
    Map a Stripe Subscription to a billable tier (free / pro / elite).
    Uses subscription status and line-item price IDs (PRICE_MAP / env prices).
    """
    status = str(_subscription_field(subscription, "status", "") or "").lower()
    if status in {"canceled", "unpaid", "incomplete_expired", "incomplete"}:
        return "free"

    items_obj = _subscription_field(subscription, "items")
    lines: list[Any] = []
    if isinstance(items_obj, dict):
        lines = list(items_obj.get("data") or [])
    else:
        lines = list(getattr(items_obj, "data", None) or [])
    tier_rank = {"free": 0, "pro": 1, "elite": 2}
    best = "free"
    for item in lines:
        price = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
        pid = ""
        if isinstance(price, str):
            pid = price
        elif isinstance(price, dict):
            pid = str(price.get("id") or "")
        elif price is not None:
            pid = str(getattr(price, "id", "") or "")
        t = _tier_for_price_id(pid)
        if t and tier_rank.get(t, 0) > tier_rank.get(best, 0):
            best = t

    if best != "free":
        return best

    meta = _metadata_from_stripe_object(_subscription_field(subscription, "metadata"))
    meta_tier = (meta.get("tier") or "").strip().lower()
    if meta_tier in {"pro", "elite"}:
        return meta_tier

    return "free"


def downgrade_user_to_free(db: Session, username: str, *, subscription_id: str | None = None) -> Any:
    """Set user.tier to free after subscription removal (preserves internal dev tier)."""
    user = db.query(_app.User).filter(_app.User.username == username).first()
    if not user:
        return None
    if str(getattr(user, "tier", "") or "").strip().lower() == "dev":
        return user
    stored = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    eid = (subscription_id or "").strip()
    if eid and stored and stored != eid:
        return user
    user.tier = "free"
    if hasattr(user, "stripe_subscription_id"):
        user.stripe_subscription_id = None
    db.commit()
    db.refresh(user)
    return user


def sync_user_tier_from_stripe_subscription(
    db: Session,
    username: str,
    tier: str,
    *,
    stripe_subscription_id: str | None = None,
) -> Any:
    """Apply tier from Stripe subscription state (free / pro / elite). Preserves dev tier."""
    user = db.query(_app.User).filter(_app.User.username == username).first()
    if not user:
        return None
    if str(getattr(user, "tier", "") or "").strip().lower() == "dev":
        return user
    desired = (tier or "").strip().lower()
    if desired not in {"free", "pro", "elite"}:
        desired = "free"
    user.tier = desired
    sid = (stripe_subscription_id or "").strip()
    if hasattr(user, "stripe_subscription_id"):
        if desired == "free":
            user.stripe_subscription_id = None
        elif sid:
            user.stripe_subscription_id = sid[:128]
    db.commit()
    db.refresh(user)
    return user


def apply_subscription_deleted(db: Session, subscription: Any) -> tuple[str, str]:
    sub_id = str(_subscription_field(subscription, "id", "") or "").strip()
    username = subscription_username(subscription)

    if not username:
        customer_id = str(_subscription_field(subscription, "customer", "") or "").strip()
        if customer_id and _app.STRIPE_KEY:
            try:
                cust = stripe.Customer.retrieve(customer_id)
                meta = _metadata_from_stripe_object(getattr(cust, "metadata", None))
                username = (meta.get("username") or "").strip()
            except Exception:
                username = ""

    if not username:
        return "skipped", f"Missing username for subscription {sub_id}"

    user = (
        db.query(_app.User)
        .filter(_app.User.username == username)
        .with_for_update()
        .first()
    )
    if not user:
        return "skipped", f"User not found: {username!r} subscription={sub_id}"

    if str(getattr(user, "tier", "") or "").strip().lower() == "dev":
        return "ok", f"Preserved dev tier for {username} subscription={sub_id}"

    stored = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    if stored and stored != sub_id:
        return (
            "skipped",
            f"Subscription {sub_id} does not match user's active sub — not downgrading",
        )

    user.tier = "free"
    if hasattr(user, "stripe_subscription_status"):
        user.stripe_subscription_status = "canceled"
    if hasattr(user, "stripe_tier_source"):
        user.stripe_tier_source = "webhook"
    db.commit()
    db.refresh(user)
    return "ok", f"Downgraded {username} to free subscription={sub_id}"


def apply_subscription_updated(db: Session, subscription: Any) -> tuple[str, str]:
    sub_id = str(getattr(subscription, "id", "") or "")
    sub_status = str(getattr(subscription, "status", "") or "")
    metadata = getattr(subscription, "metadata", {}) or {}
    username = ""
    try:
        username = str((metadata or {}).get("username", "") or "")
    except Exception:
        username = ""
    username = username.strip()

    if not username:
        return "skipped", f"Missing username in subscription metadata subscription={sub_id}"

    user = (
        db.query(_app.User)
        .filter(_app.User.username == username)
        .with_for_update()
        .first()
    )
    if not user:
        return "skipped", f"User not found: {username!r} subscription={sub_id}"

    status_norm = sub_status.strip().lower()
    if status_norm in {"past_due", "unpaid"}:
        if hasattr(user, "stripe_subscription_status"):
            user.stripe_subscription_status = status_norm
        db.commit()
        logger.warning("subscription_payment_issue username=%s status=%s", username, status_norm)
        return (
            "payment_issue",
            f"Subscription {sub_id} is {status_norm} — tier held pending retry",
        )

    if status_norm == "canceled":
        return apply_subscription_deleted(db, subscription)

    if status_norm == "active":
        tier = infer_tier_from_subscription(subscription)
        if tier and tier != "free":
            apply_successful_upgrade(
                db,
                username,
                tier,
                stripe_subscription_id=(sub_id or None),
                tier_source="webhook",
            )
            if hasattr(user, "stripe_subscription_status"):
                user.stripe_subscription_status = "active"
            db.commit()
            db.refresh(user)
            return "ok", f"Synced {username} to tier={tier} subscription={sub_id}"

        if hasattr(user, "stripe_subscription_status"):
            user.stripe_subscription_status = "active"
        db.commit()
        return "ok", f"Subscription {sub_id} active — no tier change"

    if status_norm in {"trialing", "incomplete"}:
        if hasattr(user, "stripe_subscription_status"):
            user.stripe_subscription_status = status_norm
        db.commit()
        return "ok", f"Subscription {sub_id} trialing/incomplete — no tier change"

    if hasattr(user, "stripe_subscription_status"):
        user.stripe_subscription_status = status_norm
    db.commit()
    return "ok", f"Subscription {sub_id} updated status={sub_status}"


def validate_plan_access(user: Any) -> dict[str, Any]:
    """
    Returns whether the user's current tier is considered valid.
    A free-tier user is always valid.
    A pro/elite user is valid if stripe_subscription_status is "active" or "trialing"
    OR if stripe_tier_source is "manual" (manually granted by admin).
    """
    tier = str(getattr(user, "tier", "free") or "free").strip().lower()
    if tier in {"free", "dev"}:
        return {"valid": True, "tier": tier, "reason": "free_tier"}

    sub_status = str(getattr(user, "stripe_subscription_status", "") or "").strip().lower()
    tier_source = str(getattr(user, "stripe_tier_source", "") or "").strip().lower()

    if tier_source == "manual":
        return {"valid": True, "tier": tier, "reason": "manually_granted"}

    if sub_status in {"active", "trialing"}:
        return {"valid": True, "tier": tier, "reason": "active_subscription"}

    if sub_status in {"past_due", "unpaid"}:
        return {"valid": True, "tier": tier, "reason": "grace_period", "warning": "payment_due"}

    if sub_status in {"canceled", "incomplete_expired"}:
        return {"valid": False, "tier": tier, "reason": "subscription_ended"}

    return {"valid": True, "tier": tier, "reason": "status_unknown", "warning": "subscription_status_unverified"}
