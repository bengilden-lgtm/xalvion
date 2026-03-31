"""
agents.py — thin public interface over the real agent pipeline.

FIX: Original was a dead stub (hello/help string matching) that existed
     alongside the real agent.py but did nothing useful.  This version
     delegates to run_agent() so any caller that imports from agents.py
     gets the full Xalvion pipeline.
"""
from __future__ import annotations

from typing import Any, Dict

from agent import run_agent as _run_agent


def process_message(
    message: str,
    user_id: str = "default-user",
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Process a support message through the full Xalvion pipeline.

    Returns the same structured dict as agent.run_agent().
    """
    return _run_agent(message, user_id=user_id, meta=meta or {})


def run_agent(
    message: str,
    user_id: str = "default-user",
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Alias kept for backwards compatibility."""
    return process_message(message, user_id=user_id, meta=meta)
