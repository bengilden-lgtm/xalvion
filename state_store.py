from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Iterator

DATABASE_PATH = os.getenv("STATE_STORE_PATH", "/mnt/data/aurum.db")
_INIT_LOCK = Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=5.0, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _ensure_schema() -> None:
    with _INIT_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )
        finally:
            conn.close()


@contextmanager
def _transaction(immediate: bool = False) -> Iterator[sqlite3.Connection]:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_state(key: str, default: dict[str, Any]) -> dict[str, Any]:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default.copy()
        try:
            parsed = json.loads(row["value"])
            return parsed if isinstance(parsed, dict) else default.copy()
        except Exception:
            return default.copy()
    finally:
        conn.close()


def save_state(key: str, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False)
    now = datetime.utcnow().isoformat()
    with _transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload, now),
        )


def mutate_state(key: str, default: dict[str, Any], mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    with _transaction(immediate=True) as conn:
        row = conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            current = default.copy()
        else:
            try:
                parsed = json.loads(row["value"])
                current = parsed if isinstance(parsed, dict) else default.copy()
            except Exception:
                current = default.copy()
        updated = mutator(current)
        conn.execute(
            """
            INSERT INTO agent_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, json.dumps(updated, ensure_ascii=False), datetime.utcnow().isoformat()),
        )
        return updated
