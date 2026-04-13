import hashlib
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("xalvion.tools")

# ---------------------------------------------------------------------------
# Order / shipment data integrity
# ---------------------------------------------------------------------------
# Mock catalog and scenario generators are ONLY used when XALVION_DEMO_MODE
# is enabled. Production paths must never fabricate tracking, ETAs, or status.

NO_LIVE_ORDER_MESSAGE = "No live order data connected"

# Demo-only fixed personas (see is_demo_mode()).
ORDERS = {
    "John": {"status": "shipped", "value": 120, "tracking": "TRK-1001", "eta": "2-4 business days"},
    "Sarah": {"status": "delayed", "value": 80, "tracking": "TRK-1002", "eta": "Delayed in transit"},
    "Mike": {"status": "delivered", "value": 200, "tracking": "TRK-1003", "eta": "Delivered"},
    "Emma": {"status": "processing", "value": 150, "tracking": "TRK-1004", "eta": "Preparing for dispatch"},
}


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def is_demo_mode() -> bool:
    """Explicit opt-in for mock orders, tracking, and ETAs (sales demos / local dev only)."""
    return _truthy_env("XALVION_DEMO_MODE")


def _shopify_credentials_configured() -> bool:
    shop = (os.getenv("SHOPIFY_SHOP_DOMAIN", "") or "").strip().rstrip("/")
    token = (os.getenv("SHOPIFY_ACCESS_TOKEN", "") or "").strip()
    return bool(shop and token)


def live_order_integration_configured() -> bool:
    """
    True when this process is configured to use a real order/shipment backend.

    Today that means live tool mode plus Shopify admin credentials plus an
    explicit opt-in to read order data (XALVION_LIVE_ORDER_DATA). The live fetch
    path must return real API fields — never placeholders.
    """
    exec_mode = (os.getenv("XALVION_EXEC_MODE", "") or "").strip().lower()
    if exec_mode != "live":
        return False
    if not _shopify_credentials_configured():
        return False
    return _truthy_env("XALVION_LIVE_ORDER_DATA")


def _stable_seed(name: str) -> int:
    return int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)


def _default_mock_order(customer: str) -> dict[str, Any]:
    seed = _stable_seed((customer or "guest").strip()) % 4
    options = [
        {"status": "processing", "value": 99, "tracking": "TRK-DEV-201", "eta": "Preparing for dispatch"},
        {"status": "shipped", "value": 129, "tracking": "TRK-DEV-202", "eta": "2-4 business days"},
        {"status": "delayed", "value": 149, "tracking": "TRK-DEV-203", "eta": "Delayed in transit"},
        {"status": "delivered", "value": 89, "tracking": "TRK-DEV-204", "eta": "Delivered"},
    ]
    return options[seed]


def _scenario_mock_order(customer: str, context: str) -> dict[str, Any]:
    text = (context or "").lower()
    seed = _stable_seed((customer or "guest").strip()) % 1000

    delivered_missing = any(
        p
        in text
        for p in [
            "delivered but i never got it",
            "delivered but i didnt get it",
            "delivered but i didn't get it",
            "says delivered but i never got it",
            "says delivered but i didnt get it",
            "says delivered but i didn't get it",
            "not received",
            "never got it",
            "missing package",
            "missing parcel",
            "stolen",
        ]
    )

    late_or_delayed = any(
        p
        in text
        for p in [
            "late",
            "delayed",
            "where is my order",
            "where's my order",
            "wheres my order",
            "where is my package",
            "where's my package",
            "wheres my package",
            "still not here",
            "taking too long",
            "annoyed",
            "tracking not moving",
        ]
    )

    shipped_intent = any(p in text for p in ["shipped", "in transit", "tracking", "on the way"])

    processing_intent = any(
        p in text for p in ["processing", "hasn't shipped", "hasnt shipped", "not shipped", "preparing"]
    )

    if delivered_missing:
        return {
            "status": "delivered",
            "value": 119,
            "tracking": f"TRK-DEV-{700 + (seed % 100)}",
            "eta": "Delivered",
        }

    if late_or_delayed:
        return {
            "status": "delayed",
            "value": 139,
            "tracking": f"TRK-DEV-{500 + (seed % 100)}",
            "eta": "Delayed in transit",
        }

    if processing_intent:
        return {
            "status": "processing",
            "value": 109,
            "tracking": f"TRK-DEV-{300 + (seed % 100)}",
            "eta": "Preparing for dispatch",
        }

    if shipped_intent:
        return {
            "status": "shipped",
            "value": 129,
            "tracking": f"TRK-DEV-{400 + (seed % 100)}",
            "eta": "2-4 business days",
        }

    return _default_mock_order(customer)


def _normalize_order_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(raw.get("status", "") or "").strip(),
        "value": int(raw.get("value", 0) or 0),
        "tracking": str(raw.get("tracking", "") or "").strip(),
        "eta": str(raw.get("eta", "") or "").strip(),
    }


def _fetch_live_order_snapshot(customer: str, context: str) -> dict[str, Any] | None:
    """
    Pull order/shipment facts from the configured backend.

    Returns a normalized dict only when real data exists for the request.
    Intentionally conservative: no customer-scoped Shopify lookup is wired yet,
    so this returns None and callers surface NO_LIVE_ORDER_MESSAGE instead of
    inventing logistics fields.
    """
    if not live_order_integration_configured():
        return None
    # Future: Shopify (or other) customer/order lookup using `customer`, request context, etc.
    _ = (customer, context)
    return None


def get_order(customer: str, context: Optional[str] = None) -> dict[str, Any]:
    """
    Order context for the agent. Non-demo paths never fabricate tracking or ETAs.

    - Demo mode (XALVION_DEMO_MODE): synthetic catalog / scenarios for demos.
    - Live order reads: enabled only when live_order_integration_configured()
      and _fetch_live_order_snapshot returns data (not yet implemented).
    - Otherwise: connected=False and a truthful disconnected payload.
    """
    ctx = context or ""

    if is_demo_mode():
        if customer in ORDERS:
            base = _normalize_order_payload(ORDERS[customer])
        else:
            base = _normalize_order_payload(_scenario_mock_order(customer, ctx))
        return {
            **base,
            "connected": True,
            "source": "demo",
            "message": "",
        }

    live = _fetch_live_order_snapshot(customer, ctx)
    if live:
        base = _normalize_order_payload(live)
        return {
            **base,
            "connected": True,
            "source": "live",
            "message": "",
        }

    return {
        "status": "",
        "value": 0,
        "tracking": "",
        "eta": "",
        "connected": False,
        "source": "none",
        "message": NO_LIVE_ORDER_MESSAGE,
    }


def process_refund(customer, amount):
    try:
        amt = int(amount or 0)
    except (TypeError, ValueError):
        amt = 0
    if amt > 500_000:
        return {"error": "Refund exceeds safe limit", "mock": True, "verified": False}

    return {
        "status": "success",
        "customer": customer,
        "amount": amt,
        "mock": True,
        "verified": False,
    }


def issue_credit(customer, amount):
    return {
        "status": "credit_issued",
        "customer": customer,
        "amount": amount,
        "mock": True,
        "verified": False,
    }


# ---------------------------------------------------------------------------
# Dual-mode execution (financial tools)
# ---------------------------------------------------------------------------
# Set XALVION_EXEC_MODE=live in production to route through real APIs.
# Default is "mock" — refund/credit simulators unless live mode is enabled.

_EXEC_MODE = (os.getenv("XALVION_EXEC_MODE", "mock") or "mock").strip().lower()


def execute_tool(
    action: str,
    payload: dict,
    mode: Optional[str] = None,
) -> dict:
    """
    Dual-mode tool dispatcher.

    mode="mock" (default): local refund/credit simulators; get_order respects
    demo mode and never returns synthetic logistics when demo is off.

    mode="live": real Shopify APIs (requires env vars) for financial actions.

    Fails safely: any live error returns {"status": "live_error", ...}
    which the caller treats as requires_approval=True → review queue.
    """
    effective_mode = (mode or _EXEC_MODE or "mock").strip().lower()

    if effective_mode != "live":
        if action == "refund":
            return process_refund(
                payload.get("customer", ""),
                payload.get("amount", 0),
            )
        if action == "credit":
            return issue_credit(
                payload.get("customer", ""),
                payload.get("amount", 0),
            )
        if action == "get_order":
            return get_order(
                str(payload.get("customer", "") or ""),
                payload.get("context"),
            )
        return {"status": "no_action", "mode": "mock", "mock": True, "verified": False}

    try:
        return _live_dispatch(action, payload)
    except Exception as _exc:
        logger.warning("live_tool_dispatch_failed action=%s detail=%s", action, str(_exc)[:200])
        return {
            "status": "live_error",
            "error": str(_exc)[:500],
            "fallback": "review",
            "mode": "live",
        }


def _live_dispatch(action: str, payload: dict) -> dict:
    """
    Real Shopify API dispatcher. Only active when XALVION_EXEC_MODE=live
    and SHOPIFY_SHOP_DOMAIN + SHOPIFY_ACCESS_TOKEN are set.
    """
    import time

    import requests as _req

    shop = (os.getenv("SHOPIFY_SHOP_DOMAIN", "") or "").strip().rstrip("/")
    token = (os.getenv("SHOPIFY_ACCESS_TOKEN", "") or "").strip()
    api_ver = (os.getenv("SHOPIFY_API_VERSION", "2024-04") or "2024-04").strip()

    if not shop or not token:
        raise RuntimeError(
            "SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN are required for live execution mode"
        )

    base = f"https://{shop}/admin/api/{api_ver}"
    hdrs = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def _request(method: str, path: str, body: dict | None = None, retries: int = 3) -> dict:
        url = f"{base}{path}"
        for attempt in range(retries):
            try:
                r = _req.request(method, url, headers=hdrs, json=body, timeout=12.0)
                if r.status_code == 429:
                    time.sleep(float(r.headers.get("Retry-After", 2.0)))
                    continue
                if r.status_code >= 500:
                    time.sleep(2**attempt)
                    continue
                data = r.json() if r.content else {}
                if not r.ok:
                    err = data.get("errors") or data.get("error") or r.text[:200]
                    raise RuntimeError(f"Shopify {r.status_code}: {err}")
                return data
            except RuntimeError:
                raise
            except Exception as exc:
                if attempt == retries - 1:
                    raise RuntimeError(str(exc)) from exc
                time.sleep(2**attempt)
        raise RuntimeError("Shopify request failed after all retries")

    if action == "refund":
        amount = round(float(payload.get("amount", 0) or 0), 2)
        order_id = str(payload.get("order_id", "") or "").strip()
        if not order_id:
            return {"status": "error", "error": "order_id required for live refund", "mode": "live"}
        body = {
            "refund": {
                "currency": "USD",
                "notify": True,
                "note": "Xalvion auto-refund",
                "transactions": [
                    {
                        "order_id": order_id,
                        "kind": "refund",
                        "gateway": "shopify_payments",
                        "amount": f"{amount:.2f}",
                    }
                ],
            }
        }
        data = _request("POST", f"/orders/{order_id}/refunds.json", body)
        refund = data.get("refund", {})
        return {
            "status": "success",
            "customer": payload.get("customer", ""),
            "amount": amount,
            "refund_id": str(refund.get("id", "")),
            "order_id": order_id,
            "mode": "live",
            "mock": False,
            "verified": True,
        }

    if action == "credit":
        amount = round(float(payload.get("amount", 0) or 0), 2)
        body = {
            "gift_card": {
                "initial_value": f"{amount:.2f}",
                "currency": "USD",
                "note": f"Xalvion credit for {payload.get('customer', '')}",
            }
        }
        data = _request("POST", "/gift_cards.json", body)
        gc = data.get("gift_card", {})
        return {
            "status": "credit_issued",
            "customer": payload.get("customer", ""),
            "amount": amount,
            "gift_card_id": str(gc.get("id", "")),
            "mode": "live",
            "mock": False,
            "verified": True,
        }

    if action == "get_order":
        out = dict(
            get_order(
                str(payload.get("customer", "") or ""),
                payload.get("context"),
            )
        )
        out["mode"] = "live"
        return out

    return {"status": "no_action", "mode": "live"}
