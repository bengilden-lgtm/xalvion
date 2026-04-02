from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import Column, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./aurum.db").strip()
    if not raw.startswith("sqlite:///"):
        return raw

    sqlite_target = raw.replace("sqlite:///", "", 1).strip()

    if sqlite_target.startswith("/"):
        db_path = Path(sqlite_target)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    preferred_dir = (
        os.getenv("STATE_STORE_DIR")
        or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        or "/tmp/xalvion_state"
    )
    base_dir = Path(preferred_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / sqlite_target
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = _resolve_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AgentState(Base):
    __tablename__ = "agent_state"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False, default="{}")
    updated_at = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


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
        payload = json.dumps(value, ensure_ascii=False)
        now = datetime.utcnow().isoformat()
        row = db.query(AgentState).filter(AgentState.key == key).first()
        if row is None:
            db.add(AgentState(key=key, value=payload, updated_at=now))
        else:
            row.value = payload
            row.updated_at = now
        db.commit()
    finally:
        db.close()


def mutate_state(key: str, default: dict[str, Any], mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        db.execute(text("BEGIN IMMEDIATE"))
        row = db.query(AgentState).filter(AgentState.key == key).first()
        if row is None:
            current = default.copy()
            row = AgentState(
                key=key,
                value=json.dumps(current, ensure_ascii=False),
                updated_at=datetime.utcnow().isoformat(),
            )
            db.add(row)
            db.flush()
        else:
            try:
                current = json.loads(row.value)
                if not isinstance(current, dict):
                    current = default.copy()
            except Exception:
                current = default.copy()

        updated = mutator(current)
        row.value = json.dumps(updated, ensure_ascii=False)
        row.updated_at = datetime.utcnow().isoformat()
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
