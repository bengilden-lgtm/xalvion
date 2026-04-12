from __future__ import annotations

from typing import Any

import app as app_mod


def guest_preview_snapshot(client_id: str | None) -> dict[str, Any] | None:
    """Per-preview-client usage against ``GUEST_PREVIEW_OPERATOR_LIMIT`` (read-only)."""
    gid = app_mod.normalize_guest_client_id(client_id)
    if not gid:
        return None
    with app_mod.db_session() as db:
        row = db.query(app_mod.GuestPreviewUsage).filter(app_mod.GuestPreviewUsage.client_id == gid).first()
        used = int(row.usage_count) if row else 0
    lim = int(app_mod.GUEST_PREVIEW_OPERATOR_LIMIT)
    rem = max(0, lim - used)
    return {
        "usage": used,
        "limit": lim,
        "plan_limit": lim,
        "remaining": rem,
        "preview_exhausted": rem <= 0,
    }
