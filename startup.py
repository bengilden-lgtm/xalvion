from __future__ import annotations

"""
startup.py — Idempotent DB schema migrations run at application startup.

Owns:
  - All ALTER TABLE migrations (add column if not exists)
  - One-time data migrations (memory blob → per-user keys)
  - One-time rollup migrations (legacy usage → monthly rollups)

Does NOT own:
  - Table creation (handled by SQLAlchemy create_all in db.py)
  - Application configuration
  - Business logic

Imports from:
  - db (engine, SessionLocal) — imported inside each function to avoid circular imports
"""

import logging

from sqlalchemy import text

logger = logging.getLogger("xalvion.api")


def ensure_ticket_columns() -> None:
    from sqlalchemy import inspect

    from db import engine

    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("tickets")}
        additions: list[str] = []
        if "customer_email" not in columns:
            additions.append("ALTER TABLE tickets ADD COLUMN customer_email VARCHAR(320)")
        if additions:
            with engine.begin() as conn:
                for statement in additions:
                    conn.execute(text(statement))
    except Exception as exc:
        from app import STARTUP_ISSUES  # imported lazily: shared startup issue sink

        STARTUP_ISSUES.append(f"ticket_columns_migration_failed:{type(exc).__name__}:{str(exc)[:180]}")
        logger.error("ensure_ticket_columns_failed detail=%s", str(exc)[:500], exc_info=True)


def ensure_user_columns() -> None:
    from sqlalchemy import inspect

    from db import engine

    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("users")}
        additions = []
        if "stripe_connected" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_connected INTEGER DEFAULT 0 NOT NULL")
        if "stripe_account_id" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_account_id VARCHAR")
        if "stripe_livemode" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_livemode INTEGER DEFAULT 0 NOT NULL")
        if "stripe_scope" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_scope VARCHAR")
        if "stripe_subscription_id" not in columns:
            additions.append("ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(128)")
        if additions:
            with engine.begin() as conn:
                for statement in additions:
                    conn.execute(text(statement))
    except Exception as exc:
        from app import STARTUP_ISSUES  # imported lazily: shared startup issue sink

        STARTUP_ISSUES.append(f"user_columns_migration_failed:{type(exc).__name__}:{str(exc)[:180]}")
        logger.error("ensure_user_columns_failed detail=%s", str(exc)[:500], exc_info=True)


def ensure_user_role_column() -> None:
    """Add the ``role`` column to the users table if it does not exist yet (idempotent)."""
    from db import engine

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'operator'"))
        logger.info("ensure_user_role_column: role column added")
    except Exception:
        # Column already exists — this is the expected path after first migration.
        pass


def ensure_stripe_status_columns() -> None:
    from db import engine

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN stripe_subscription_status VARCHAR"
                )
            )
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN stripe_tier_source VARCHAR DEFAULT 'manual'"
                )
            )
    except Exception:
        pass


def migrate_memory_blob_to_per_user_keys() -> None:
    # NOTE: Present as a named startup migration hook for backward compatibility with deployments
    # that previously ran this migration. Current codebase has no legacy memory blob state to move.
    return None


def migrate_legacy_operator_usage_into_rollups() -> None:
    """One-time style migration: seed monthly rollups from legacy ``users.usage`` when rollups are empty."""
    try:
        from app import STARTUP_ISSUES, operator_billing_period_key, account_operator_usage_sum
        from orm_app_tables import OperatorMonthlyUsage
        from orm_models import User
        from db import SessionLocal

        period = operator_billing_period_key()
        db = SessionLocal()
        try:
            for u in db.query(User).all():
                uname = str(getattr(u, "username", "") or "").strip()
                if not uname or uname in {"guest", "dev_user"}:
                    continue
                if account_operator_usage_sum(db, uname, period) > 0:
                    continue
                legacy = int(getattr(u, "usage", 0) or 0)
                if legacy <= 0:
                    continue
                db.merge(
                    OperatorMonthlyUsage(
                        account_username=uname[:96],
                        workspace_id="default",
                        period_key=period,
                        run_count=legacy,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:
        from app import STARTUP_ISSUES  # imported lazily: shared startup issue sink

        STARTUP_ISSUES.append(f"operator_usage_migration_failed:{type(exc).__name__}:{str(exc)[:180]}")
        logger.warning("migrate_legacy_operator_usage_failed detail=%s", str(exc)[:400], exc_info=True)

