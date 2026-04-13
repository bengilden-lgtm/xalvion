from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from growth_insights import append_insight

router = APIRouter(tags=["growth"])

logger = logging.getLogger("xalvion.api")


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
    body: GrowthEventIn,
    authorization: str | None = Header(None),
    x_guest: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    """Client-side funnel signals (tickets, approvals, auto-path, etc.)."""
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
    body: GrowthFeedbackIn,
    authorization: str | None = Header(None),
    x_guest: str | None = Header(None, alias="X-Xalvion-Guest-Client"),
):
    """Post–first-success qualitative feedback."""
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
