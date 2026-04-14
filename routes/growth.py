from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from growth_insights import append_insight

router = APIRouter(tags=["growth"])

logger = logging.getLogger("xalvion.api")

# In-process fallback rate-limit store for growth endpoints (IP-keyed, 20 req/60s).
_growth_rate_log: dict[str, list[float]] = {}
_GROWTH_RATE_LIMIT = 20
_GROWTH_RATE_WINDOW = 60.0


def _growth_check_rate_limit(ip: str) -> bool:
    """
    IP-keyed sliding-window rate limiter for unauthenticated growth endpoints.
    Returns True if the request is allowed, False if the limit is exceeded.
    Delegates to the DB-backed check_rate_limit when available; falls back to
    an in-process dict so callers never crash.
    """
    key = f"growth_ip:{(ip or 'unknown')[:64]}"
    try:
        import app as app_mod
        return app_mod.check_rate_limit(key)
    except Exception:
        pass
    # In-process fallback
    # Divide limit by assumed worker count for multi-process safety.
    # The DB-backed path (primary) is process-safe; this fallback intentionally
    # uses a lower cap.
    _EFFECTIVE_FALLBACK_LIMIT = max(1, _GROWTH_RATE_LIMIT // 2)
    now = time.time()
    cutoff = now - _GROWTH_RATE_WINDOW
    _growth_rate_log.setdefault(key, [])
    _growth_rate_log[key] = [t for t in _growth_rate_log[key] if t >= cutoff]
    if len(_growth_rate_log[key]) >= _EFFECTIVE_FALLBACK_LIMIT:
        return False
    _growth_rate_log[key].append(now)
    return True


class GrowthEventIn(BaseModel):
    type: str = Field(..., max_length=96)
    props: dict[str, Any] = Field(default_factory=dict)


class GrowthFeedbackIn(BaseModel):
    useful: str | None = Field(None, max_length=32)
    pay_for: str = Field("", max_length=2000)
    context: str = Field("", max_length=256)


def _actor_from_headers(
    authorization: str | None,
    x_guest: str | None,
) -> str:
    import app as app_mod

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            try:
                username = app_mod.decode_token(token)
                if username:
                    return str(username)[:120]
            except Exception:
                pass
    g = (x_guest or "").strip()
    if g:
        return f"guest:{g[:80]}"
    return "anonymous"


@router.post("/growth/event")
def ingest_growth_event(
    request: Request,
    body: GrowthEventIn,
    authorization: str | None = Header(None),
    x_guest: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    """Client-side funnel signals (tickets, approvals, auto-path, etc.)."""
    ip = (request.client.host if request.client else None) or "unknown"
    if not _growth_check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    actor = _actor_from_headers(authorization, x_guest)
    props = body.props if isinstance(body.props, dict) else {}
    slim: dict[str, Any] = {}
    for k, v in list(props.items())[:40]:
        key = str(k)[:64]
        if isinstance(v, (int, float, bool)) or v is None:
            slim[key] = v
        else:
            slim[key] = str(v)[:500]
    append_insight(body.type.strip()[:96], actor=actor, props=slim)
    return {"ok": True}


@router.post("/growth/feedback")
def ingest_growth_feedback(
    request: Request,
    body: GrowthFeedbackIn,
    authorization: str | None = Header(None),
    x_guest: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    """Post–first-success qualitative feedback."""
    ip = (request.client.host if request.client else None) or "unknown"
    if not _growth_check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    actor = _actor_from_headers(authorization, x_guest)
    append_insight(
        "feedback",
        actor=actor,
        props={
            "useful": (body.useful or "")[:32],
            "pay_for": (body.pay_for or "")[:2000],
            "context": (body.context or "")[:256],
        },
    )
    return {"ok": True}
