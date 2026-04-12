"""
Fail if the FastAPI app registers the same (method, path) more than once.

Duplicate decorators (e.g. the same path on ``app`` and on ``routes.*``) are
easy to miss and make "authoritative" behavior depend on registration order.
"""
from __future__ import annotations

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


def test_no_duplicate_method_path_pairs():
    keys = _route_keys()
    counts = Counter(keys)
    duplicates = sorted([k for k, n in counts.items() if n > 1])
    assert not duplicates, f"Duplicate route registrations: {duplicates}"


def test_expected_routers_are_wired():
    """Sanity check that modular routers still contribute core workspace paths."""
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
