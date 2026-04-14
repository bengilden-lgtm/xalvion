from __future__ import annotations

import os


# Ensure test runs never import the app with production/live billing settings.
# This must execute at import time (before test modules import `app`).
os.environ["ENVIRONMENT"] = "development"
os.environ["XALVION_EXEC_MODE"] = "live"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ.setdefault("SHOPIFY_SHOP_DOMAIN", "example.myshopify.com")
os.environ.setdefault("SHOPIFY_ACCESS_TOKEN", "dummy_token_for_tests")

# app.py calls `load_dotenv(override=True)` at import time, which can overwrite the
# test environment from a local `.env` (including live Stripe keys / production flags).
# Patch it to a no-op for the test process before `app` is imported.
try:
    import dotenv  # type: ignore

    def _no_dotenv(*_a, **_k):
        return False

    dotenv.load_dotenv = _no_dotenv  # type: ignore[attr-defined]
except Exception:
    pass

# In live execution mode, tools dispatch to Shopify APIs. For unit tests we
# must not perform network calls; stub financial tool execution to succeed.
try:
    import tools  # type: ignore

    _real_execute_tool = tools.execute_tool

    def _execute_tool_stub(action: str, payload: dict, mode=None):  # type: ignore[override]
        if (mode or tools.get_execution_mode() or "mock").strip().lower() == "live" and action in {"refund", "credit"}:
            return {"status": "success", "mode": "live", "mock": False, "verified": True}
        return _real_execute_tool(action, payload, mode=mode)

    tools.execute_tool = _execute_tool_stub  # type: ignore[assignment]
except Exception:
    pass
