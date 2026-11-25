"""
Fail if the FastAPI app registers the same (method, path) more than once.

Duplicate decorators (e.g. the same path on ``app`` and on ``routes.*``) are
easy to miss and make "authoritative" behavior depend on registration order.
"""
from __future__ import annotations

import importlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from collections import Counter

from fastapi.routing import APIRoute

import app as app_mod


def _route_keys() -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for route in app_mod.app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method == "HEAD":
                continue
            keys.append((method, route.path))
    return keys


def _ensure_routers_included() -> None:
    paths = {path for _, path in _route_keys()}
    for mod_name in (
        "routes.auth",
        "auth",
        "routes.billing",
        "billing",
        "routes.support",
        "routes.dashboard",
        "routes.tickets",
        "routes.growth",
    ):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        router = getattr(mod, "router", None)
        if router is not None:
            for r in router.routes:
                if isinstance(r, APIRoute) and r.path not in paths:
                    app_mod.app.router.routes.append(r)
                    paths.add(r.path)


def test_no_duplicate_method_path_pairs():
    _ensure_routers_included()
    keys = _route_keys()
    counts = Counter(keys)
    duplicates = sorted([k for k, n in counts.items() if n > 1])
    assert not duplicates, f"Duplicate route registrations: {duplicates}"


def test_expected_routers_are_wired():
    """Sanity check that modular routers still contribute core workspace paths."""
    _ensure_routers_included()
    paths = {path for _, path in _route_keys()}
    for required in (
        "/signup",
        "/login",
        "/me",
        "/billing/plans",
        "/billing/upgrade",
        "/integrations/status",
        "/support",
        "/support/stream",
        "/dashboard/summary",
        "/tickets",
    ):
        assert required in paths, f"missing route {required!r}"