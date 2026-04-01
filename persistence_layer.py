from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Iterable

DATABASE_PATH = os.getenv("PERSISTENCE_DB_PATH", "/mnt/data/aurum.db")
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
                CREATE TABLE IF NOT EXISTS crm_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new',
                    source TEXT NOT NULL DEFAULT 'manual',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_crm_leads_user_status ON crm_leads(username, status)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    content_type TEXT NOT NULL DEFAULT 'note',
                    weight REAL NOT NULL DEFAULT 1.0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_knowledge_source_type ON knowledge_entries(source, content_type)")
        finally:
            conn.close()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(slots=True)
class LeadPayload:
    username: str
    text: str
    source: str = "manual"
    status: str = "new"
    score: int | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.username = str(self.username or "").strip()
        self.text = str(self.text or "").strip()
        self.source = str(self.source or "manual").strip() or "manual"
        self.status = str(self.status or "new").strip() or "new"
        self.score = int(self.score or 0)
        self.message = str(self.message or "")
        self.metadata = _safe_metadata(self.metadata)
        if not self.username:
            raise ValueError("username required")
        if not self.text:
            raise ValueError("text required")
        if len(self.username) > 120:
            raise ValueError("username too long")
        if len(self.text) > 5000:
            raise ValueError("text too long")


@dataclass(slots=True)
class KnowledgePayload:
    content: str
    source: str = "manual"
    content_type: str = "note"
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = str(self.content or "").strip()
        self.source = str(self.source or "manual").strip() or "manual"
        self.content_type = str(self.content_type or "note").strip() or "note"
        self.weight = float(self.weight or 1.0)
        self.metadata = _safe_metadata(self.metadata)
        if not self.content:
            raise ValueError("content required")
        if len(self.content) > 12000:
            raise ValueError("content too long")
        if not 0.0 <= self.weight <= 10.0:
            raise ValueError("weight out of range")


class LeadRepository:
    def list_all(self) -> list[dict[str, Any]]:
        _ensure_schema()
        conn = _connect()
        try:
            rows = conn.execute("SELECT * FROM crm_leads ORDER BY created_at ASC").fetchall()
            return [self._to_dict(row) for row in rows]
        finally:
            conn.close()

    def save_all(self, leads: Iterable[dict[str, Any]]) -> None:
        _ensure_schema()
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM crm_leads")
            now = _now_iso()
            for item in leads:
                payload = LeadPayload(**item)
                conn.execute(
                    """
                    INSERT INTO crm_leads (username, text, score, message, status, source, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (payload.username, payload.text, payload.score, payload.message, payload.status, payload.source, json.dumps(payload.metadata, ensure_ascii=False), now, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add(self, payload: LeadPayload) -> dict[str, Any]:
        _ensure_schema()
        conn = _connect()
        try:
            now = _now_iso()
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                INSERT INTO crm_leads (username, text, score, message, status, source, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (payload.username, payload.text, payload.score, payload.message, payload.status, payload.source, json.dumps(payload.metadata, ensure_ascii=False), now, now),
            )
            row = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (cur.lastrowid,)).fetchone()
            conn.commit()
            return self._to_dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_status(self, username: str, status: str) -> int:
        _ensure_schema()
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "UPDATE crm_leads SET status = ?, updated_at = ? WHERE username = ?",
                (status.strip(), _now_iso(), username.strip()),
            )
            conn.commit()
            return cur.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_top(self, min_score: int = 1, status: str = "new") -> list[dict[str, Any]]:
        _ensure_schema()
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM crm_leads WHERE score >= ? AND status = ? ORDER BY score DESC, created_at ASC",
                (int(min_score), status),
            ).fetchall()
            return [self._to_dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "username": row["username"],
            "text": row["text"],
            "score": row["score"],
            "message": row["message"],
            "status": row["status"],
            "source": row["source"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class KnowledgeRepository:
    def add(self, payload: KnowledgePayload) -> dict[str, Any]:
        _ensure_schema()
        conn = _connect()
        try:
            now = _now_iso()
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                INSERT INTO knowledge_entries (content, source, content_type, weight, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (payload.content, payload.source, payload.content_type, payload.weight, json.dumps(payload.metadata, ensure_ascii=False), now, now),
            )
            row = conn.execute("SELECT * FROM knowledge_entries WHERE id = ?", (cur.lastrowid,)).fetchone()
            conn.commit()
            return self._to_dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        _ensure_schema()
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_entries
                WHERE content LIKE ? OR source LIKE ? OR content_type LIKE ?
                ORDER BY weight DESC, updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, int(limit)),
            ).fetchall()
            return [self._to_dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "content": row["content"],
            "source": row["source"],
            "content_type": row["content_type"],
            "weight": row["weight"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
