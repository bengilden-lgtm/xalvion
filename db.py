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

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from threading import Lock

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


DATABASE_URL: str = _resolve_url()
_IS_SQLITE: bool = DATABASE_URL.startswith("sqlite")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_connect_args = {"check_same_thread": False} if _IS_SQLITE else {}

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


def init_db() -> None:
    """Create all tables registered on Base (idempotent). Thread-safe."""
    with _init_lock:
        Base.metadata.create_all(bind=engine)
