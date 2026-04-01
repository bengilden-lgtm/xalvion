"""Compatibility surface over the unified controller."""
from __future__ import annotations

from typing import Any, Dict

from controller import get_agent_controller


def process_message(message: str, user_id: str = "default-user", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return get_agent_controller().run_agent(message, user_id=user_id, meta=meta or {})


def run_agent(message: str, user_id: str = "default-user", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return process_message(message, user_id=user_id, meta=meta)
