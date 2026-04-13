"""Lightweight append-only growth / product signals (JSONL). Not a full analytics stack."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("xalvion.growth")

GROWTH_LOG = "growth_insights.jsonl"


def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()


def append_insight(
    event: str,
    *,
    actor: str = "",
    props: dict[str, Any] | None = None,
) -> None:
    """Append one JSON line. Never raises to callers — failures are logged once per process."""
    ev = (event or "unknown").strip()[:96] or "unknown"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": ev,
        "actor": (actor or "")[:160],
        "props": props if isinstance(props, dict) else {},
    }
    path = os.path.join(_base_dir(), GROWTH_LOG)
    line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        logger.warning("growth_insights_append_failed path=%s", path, exc_info=True)


def log_conversion_paid(username: str, tier: str, trigger: str | None = None) -> None:
    append_insight(
        "conversion_paid",
        actor=username,
        props={"tier": (tier or "").strip().lower()[:32], "trigger": (trigger or "")[:200]},
    )
