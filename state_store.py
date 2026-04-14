"""
state_store.py — SQLAlchemy-backed persistence for simple state and auxiliary stores.

Owns:
  - AgentState key/value store (load_state, save_state, mutate_state)
  - Legacy CRM/knowledge repositories that were previously in persistence_layer.py

Does NOT own:
  - FastAPI application wiring (app.py)
  - Plan configuration (plan_config.py)
  - Financial policy (governor.py)

Imports from:
  - db (Base, SessionLocal, engine)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from sqlalchemy import Column, Float, Index, Integer, String, Text

from db import Base, SessionLocal, engine


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class AgentState(Base):
    __tablename__ = "agent_state"

    key        = Column(String(120), primary_key=True)
    value      = Column(Text, nullable=False, default="{}")
    updated_at = Column(String(32), nullable=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_state(key: str, default: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = db.query(AgentState).filter(AgentState.key == key).first()
        if row is None:
            return default.copy()
        try:
            parsed = json.loads(row.value)
            return parsed if isinstance(parsed, dict) else default.copy()
        except Exception:
            return default.copy()
    finally:
        db.close()


def save_state(key: str, value: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        now     = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(value, ensure_ascii=False)

        row = db.query(AgentState).filter(AgentState.key == key).first()
        if row is None:
            db.add(AgentState(key=key, value=payload, updated_at=now))
        else:
            row.value      = payload
            row.updated_at = now

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mutate_state(
    key:     str,
    default: dict[str, Any],
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """
    Load → mutate → save in a single session.
    Uses a session-level transaction for safety; avoids BEGIN IMMEDIATE
    which is SQLite-specific and incompatible with Postgres.
    """
    db = SessionLocal()
    try:
        row = db.query(AgentState).filter(AgentState.key == key).first()

        if row is None:
            current = default.copy()
            row = AgentState(
                key=key,
                value=json.dumps(current, ensure_ascii=False),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(row)
        else:
            try:
                current = json.loads(row.value)
                if not isinstance(current, dict):
                    current = default.copy()
            except Exception:
                current = default.copy()

        updated = mutator(current)

        row.value      = json.dumps(updated, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc).isoformat()

        db.commit()
        return updated

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Legacy CRM leads + knowledge store (formerly persistence_layer.py)
# ---------------------------------------------------------------------------

class CRMLead(Base):
    __tablename__ = "crm_leads"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(120), nullable=False)
    text          = Column(Text, nullable=False)
    score         = Column(Integer, nullable=False, default=0)
    message       = Column(Text, nullable=False, default="")
    status        = Column(String(32), nullable=False, default="new")
    source        = Column(String(64), nullable=False, default="manual")
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at    = Column(String(32), nullable=False)
    updated_at    = Column(String(32), nullable=False)


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    content       = Column(Text, nullable=False)
    source        = Column(String(64), nullable=False, default="manual")
    content_type  = Column(String(64), nullable=False, default="note")
    weight        = Column(Float, nullable=False, default=1.0)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at    = Column(String(32), nullable=False)
    updated_at    = Column(String(32), nullable=False)


# Ensure indexes exist
Index("ix_crm_leads_user_status",     CRMLead.username, CRMLead.status)
Index("ix_knowledge_source_type",     KnowledgeEntry.source, KnowledgeEntry.content_type)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _row_to_lead(row: CRMLead) -> dict[str, Any]:
    return {
        "username":   row.username,
        "text":       row.text,
        "score":      row.score,
        "message":    row.message,
        "status":     row.status,
        "source":     row.source,
        "metadata":   json.loads(row.metadata_json or "{}"),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _row_to_knowledge(row: KnowledgeEntry) -> dict[str, Any]:
    return {
        "content":      row.content,
        "source":       row.source,
        "content_type": row.content_type,
        "weight":       row.weight,
        "metadata":     json.loads(row.metadata_json or "{}"),
        "created_at":   row.created_at,
        "updated_at":   row.updated_at,
    }


@dataclass(slots=True)
class LeadPayload:
    username: str
    text:     str
    source:   str              = "manual"
    status:   str              = "new"
    score:    int | None       = None
    message:  str | None       = None
    metadata: dict[str, Any]   = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.username = str(self.username or "").strip()
        self.text     = str(self.text or "").strip()
        self.source   = str(self.source or "manual").strip() or "manual"
        self.status   = str(self.status or "new").strip() or "new"
        self.score    = int(self.score or 0)
        self.message  = str(self.message or "")
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
    content:      str
    source:       str            = "manual"
    content_type: str            = "note"
    weight:       float          = 1.0
    metadata:     dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content      = str(self.content or "").strip()
        self.source       = str(self.source or "manual").strip() or "manual"
        self.content_type = str(self.content_type or "note").strip() or "note"
        self.weight       = float(self.weight or 1.0)
        self.metadata     = _safe_metadata(self.metadata)
        if not self.content:
            raise ValueError("content required")
        if len(self.content) > 12000:
            raise ValueError("content too long")
        if not 0.0 <= self.weight <= 10.0:
            raise ValueError("weight out of range")


class LeadRepository:
    def list_all(self) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(CRMLead).order_by(CRMLead.created_at.asc()).all()
            return [_row_to_lead(r) for r in rows]
        finally:
            db.close()

    def save_all(self, leads: Iterable[dict[str, Any]]) -> None:
        db = SessionLocal()
        try:
            db.query(CRMLead).delete()
            now = _now_iso()
            for item in leads:
                payload = LeadPayload(**item)
                db.add(CRMLead(
                    username=payload.username,
                    text=payload.text,
                    score=payload.score,
                    message=payload.message,
                    status=payload.status,
                    source=payload.source,
                    metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                ))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add(self, payload: LeadPayload) -> dict[str, Any]:
        db = SessionLocal()
        try:
            now = _now_iso()
            row = CRMLead(
                username=payload.username,
                text=payload.text,
                score=payload.score,
                message=payload.message,
                status=payload.status,
                source=payload.source,
                metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _row_to_lead(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_status(self, username: str, status: str) -> int:
        db = SessionLocal()
        try:
            count = (
                db.query(CRMLead)
                .filter(CRMLead.username == username.strip())
                .update({"status": status.strip(), "updated_at": _now_iso()})
            )
            db.commit()
            return count
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_top(self, min_score: int = 1, status: str = "new") -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = (
                db.query(CRMLead)
                .filter(CRMLead.score >= int(min_score), CRMLead.status == status)
                .order_by(CRMLead.score.desc(), CRMLead.created_at.asc())
                .all()
            )
            return [_row_to_lead(r) for r in rows]
        finally:
            db.close()


class KnowledgeRepository:
    def add(self, payload: KnowledgePayload) -> dict[str, Any]:
        db = SessionLocal()
        try:
            now = _now_iso()
            row = KnowledgeEntry(
                content=payload.content,
                source=payload.source,
                content_type=payload.content_type,
                weight=payload.weight,
                metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _row_to_knowledge(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        normalized = (query or "").strip()
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        db = SessionLocal()
        try:
            rows = (
                db.query(KnowledgeEntry)
                .filter(
                    KnowledgeEntry.content.like(pattern)
                    | KnowledgeEntry.source.like(pattern)
                    | KnowledgeEntry.content_type.like(pattern)
                )
                .order_by(KnowledgeEntry.weight.desc(), KnowledgeEntry.updated_at.desc())
                .limit(int(limit))
                .all()
            )
            return [_row_to_knowledge(r) for r in rows]
        finally:
            db.close()
