"""
Central URL resolution for local dev and hosted deploys (Railway, Render, Fly).

- FRONTEND_PUBLIC_ORIGIN / FRONTEND_URL — browser workspace & Stripe redirect landing (checkout return, Connect UX).
- API_PUBLIC_ORIGIN / APP_ORIGIN — public base URL of this FastAPI app (OAuth / Stripe Connect callback must hit the API).

Keep this module free of FastAPI imports so tests and tooling can import it safely.
"""

from __future__ import annotations

import os
import re
from typing import List


def _strip_origin(url: str) -> str:
    return (url or "").strip().rstrip("/")


def resolve_frontend_public_origin() -> str:
    """Public origin users open in the browser for the workspace / billing return pages."""
    v = _strip_origin(os.getenv("FRONTEND_PUBLIC_ORIGIN", ""))
    if v:
        return v
    return _strip_origin(os.getenv("FRONTEND_URL", "http://127.0.0.1:8001"))


def resolve_api_public_origin() -> str:
    """Public origin of this API (callbacks, CORS self-reference, extension target)."""
    v = _strip_origin(os.getenv("API_PUBLIC_ORIGIN", ""))
    if v:
        return v
    v = _strip_origin(os.getenv("APP_ORIGIN", ""))
    if v:
        return v
    return _strip_origin(os.getenv("XALVION_LOCAL_API_ORIGIN", "http://127.0.0.1:8000"))


def parse_extra_allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    return [_strip_origin(x) for x in raw.split(",") if _strip_origin(x)]


def default_cors_origin_regex() -> str:
    """Regex allowed origins when not overridden by CORS_ORIGIN_REGEX."""
    return (
        r"^https://([a-z0-9-]+\.)?xalvion\.tech$"
        r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://[a-z0-9-]+\.up\.railway\.app$"
        r"|^https://[a-z0-9-]+\.railway\.app$"
        r"|^https://[a-z0-9-]+\.onrender\.com$"
        r"|^https://[a-z0-9-]+\.fly\.dev$"
    )


def resolve_cors_origin_regex() -> str:
    custom = (os.getenv("CORS_ORIGIN_REGEX", "") or "").strip()
    if custom:
        try:
            re.compile(custom)
        except re.error:
            return default_cors_origin_regex()
        return custom
    return default_cors_origin_regex()


def build_allowed_cors_origins(
    frontend_origin: str,
    api_origin: str,
    extras: List[str] | None = None,
) -> List[str]:
    """Deduped list of explicit CORS origins (regex handles PaaS wildcards)."""
    seed = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "https://www.xalvion.tech",
        "https://xalvion.tech",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for o in [frontend_origin, api_origin] + (extras or []) + seed:
        if not o or o in seen:
            continue
        seen.add(o)
        out.append(o)
    return out
