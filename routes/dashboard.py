from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app as app_mod

router = APIRouter(tags=["dashboard"])

logger = logging.getLogger("xalvion.api")


@router.get("/dashboard/summary")
def dashboard_summary(
    user: app_mod.User = Depends(app_mod.get_current_user),
    db: Session = Depends(app_mod.get_db),
):
    """Delegates to app.dashboard_summary_handler (single implementation, merges get_metrics())."""
    return app_mod.dashboard_summary_handler(user, db)
