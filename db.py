"""
db.py — Single shared SQLAlchemy engine for the entire application.

PROBLEM FIXED:
    persistence_layer.py, state_store.py, and analytics.py each created their
    own engine pointing at the same SQLite file.  Three concurrent connection
    pools on one SQLite database causes "database is locked" errors under any
    real load and silently drops writes.

SOLUTION:
    Every module imports `engine` and `SessionLocal` from here.  One shared
    pool (multi-checkout on SQLite via WAL + busy_timeout) avoids both
    cross-module pool contention and single-connection starvation under FastAPI.

Postgres-ready:
    Set DATABASE_URL=postgresql+psycopg2://user:pass@host/db and the rest of
    the codebase works without changes.  Remove the connect_args kwarg for
    Postgres (check_same_thread is SQLite-only).
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from threading import Lock

print("BOOT: db.py module load start", flush=True)

# SKIPPED: Requested Ticket/ActionLog indexes must be declared after the model
# classes, but this repo defines those models in `orm_models.py` (not `db.py`).
# Adding `Index(...)` objects here would either be a no-op or raise NameError at
# import time. If you want this applied, re-run Section 1 targeting `orm_models.py`.

# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

def _resolve_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./aurum.db").strip()

    if not raw.startswith("sqlite:///"):
        return raw  # Postgres or other — pass straight through

    sqlite_path_str = raw.replace("sqlite:///", "", 1).strip()

    # Absolute path supplied → ensure parent directory exists
    if sqlite_path_str.startswith("/"):
        db_path = Path(sqlite_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    # Relative path → resolve to a writable directory, preferring a mounted
    # volume on Railway / Render / Fly.io before falling back to /tmp.
    preferred_dir = (
        os.getenv("STATE_STORE_DIR")
        or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        or os.getenv("RENDER_DISK_MOUNT_PATH")
        or None
    )

    if preferred_dir:
        base = Path(preferred_dir)
        base.mkdir(parents=True, exist_ok=True)
        db_path = base / sqlite_path_str
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    # Local dev — keep relative path as-is (resolves to cwd)
    return raw


def _redact_database_url(url: str) -> str:
    """Log-safe DSN (hides password)."""
    if not url or "@" not in url:
        return url or ""
    try:
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return f"{scheme}://{rest}"
        creds, hostpart = rest.rsplit("@", 1)
        user = creds.split(":", 1)[0] if creds else ""
        return f"{scheme}://{user}:***@{hostpart}"
    except Exception:
        return "[database_url_redacted]"


DATABASE_URL: str = _resolve_url()
_IS_SQLITE: bool = DATABASE_URL.startswith("sqlite")
# VERIFICATION FIX: C5 — export IS_POSTGRES for shared backend checks
IS_POSTGRES: bool = (not _IS_SQLITE) and (DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres"))

print(
    f"BOOT: database backend={'sqlite' if _IS_SQLITE else 'non-sqlite'} url={_redact_database_url(DATABASE_URL)}",
    flush=True,
)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

if _IS_SQLITE:
    _connect_args = {"check_same_thread": False}
else:
    # Prevent indefinite TCP hang when the DB host is unroutable (common deploy misconfig).
    _db_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "12").strip() or "12")
    _db_connect_timeout = max(2, min(_db_connect_timeout, 120))
    _connect_args = {"connect_timeout": _db_connect_timeout}

# Pool sizing: a single-connection SQLite pool (pool_size=1, max_overflow=0)
# starves FastAPI under concurrent requests — each Depends(get_db), threadpool
# work, and analytics/support compete for one checkout and hit 30s pool timeout.
# WAL + busy_timeout allow multiple readers; writers briefly wait on the DB lock.
_SQLITE_POOL_SIZE = int(os.getenv("SQLITE_POOL_SIZE", "8").strip() or "8")
_SQLITE_MAX_OVERFLOW = int(os.getenv("SQLITE_MAX_OVERFLOW", "12").strip() or "12")
_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "12").strip() or "12")

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_timeout=_POOL_TIMEOUT,
    pool_size=_SQLITE_POOL_SIZE if _IS_SQLITE else 5,
    max_overflow=_SQLITE_MAX_OVERFLOW if _IS_SQLITE else 10,
)
print("BOOT: SQLAlchemy engine configured", flush=True)

# ---------------------------------------------------------------------------
# SQLite performance & safety PRAGMAs
# Applied once per physical connection, not per session.
# ---------------------------------------------------------------------------

if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA cache_size=-16000;")  # 16 MB page cache
        cur.close()

# ---------------------------------------------------------------------------
# Session factory & Base
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Metadata initialization
# ---------------------------------------------------------------------------

_init_lock = Lock()
_orm_metadata_loaded = False


def ensure_orm_metadata_imported() -> None:
    """Import every module that registers models on ``Base`` so ``create_all`` is complete.

    Safe for Railway pre-deploy: does not import ``app`` (avoids loading FastAPI stack).
    """
    global _orm_metadata_loaded
    if _orm_metadata_loaded:
        return
    print("BOOT: registering ORM models on shared Base (metadata)", flush=True)
    import orm_models  # noqa: F401

    import orm_app_tables  # noqa: F401

    for module_name in (
        "analytics",
        "outcome_store",
        "persistence_layer",
        "state_store",
        "backend.crm.outreach",
    ):
        try:
            __import__(module_name)
        except Exception as exc:
            print(
                f"BOOT: optional ORM module skipped name={module_name} err={type(exc).__name__}: {exc!s}"[:300],
                flush=True,
            )
    _orm_metadata_loaded = True
    print("BOOT: ORM metadata import pass complete", flush=True)


def validate_db_config() -> None:
    import os as _os
    import warnings as _warnings
    try:
        workers = int(_os.getenv("WEB_CONCURRENCY", "1") or 1)
    except Exception:
        workers = 1
    if _IS_SQLITE and workers > 1:
        _warnings.warn(
            "SQLite with WEB_CONCURRENCY > 1 is unsafe. "
            "Set DATABASE_URL to a Postgres connection string before scaling workers.",
            RuntimeWarning,
            stacklevel=2,
        )


def init_db() -> None:
    """Create all tables registered on Base (idempotent). Thread-safe.
    
    Handles the multi-worker race gracefully: if another worker already
    created a type or table, the duplicate/already-exists error is caught
    and ignored. Any other error is re-raised as before.
    """
    with _init_lock:
        ensure_orm_metadata_imported()
        print("BOOT: init_db create_all starting", flush=True)
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err or "duplicate" in err:
                pass  # another worker already created tables — safe to ignore
            else:
                raise
        try:
            validate_db_config()
        except Exception:
            pass
        print("BOOT: db initialized (create_all finished)", flush=True)
