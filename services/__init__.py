"""Service-layer modules (mail, Stripe, tickets, preview quotas).

Submodules are loaded on demand so ``import services`` does not pull the full
import graph (notably ``stripe_service`` → ``app``) until those modules are used.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = (
    "email_service",
    "guest_preview_service",
    "stripe_service",
    "ticket_service",
)


def __getattr__(name: str) -> Any:
    if name in __all__:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
