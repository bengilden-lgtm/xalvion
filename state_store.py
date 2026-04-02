"""
state_store.py — Generic key-value state store backed by SQLAlchemy.

FIX: Was creating its own engine.  Now imports the shared engine from db.py
so all writes go through the same connection pool.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import Column, String, Text

from db import Base, SessionLocal, engine


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class AgentState(Base):
    __tablename__ = "agent_state"

    key        = Column(String(120), primary_key=True)
    value      = Column(Text, nullable=False, default="{}")
    updated_at = Column(String(32), nullable=False)


Base.metadata.create_all(bind=engine)


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
