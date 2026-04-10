"""
Xalvion Backend — CRM/Outreach
Owner: backend/crm

Purpose:
- Own the outreach CRM queue persistence + derived revenue metrics.
- Register the existing `/leads/*`, `/crm/*`, and `/analytics/metrics` endpoints.

Design notes:
- This module is intentionally dependency-injected to avoid importing `app.py` (no circular deps).
- Public HTTP surface area MUST remain stable (routes/JSON shape) when refactoring.
"""

from __future__ import annotations

import json
import logging
import uuid
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import Column, Integer, String, Text, Float, func

from db import Base, SessionLocal

logger = logging.getLogger("xalvion.crm.outreach")


class OutreachLeadRow(Base):
    """
    DB-backed persistence for the outreach CRM queue.
    Stores the original lead dict as JSON while duplicating key fields for sorting/metrics.
    """

    __tablename__ = "crm_outreach_leads"

    id = Column(String(64), primary_key=True)
    payload_json = Column(Text, nullable=False, default="{}")

    # Query-friendly columns (kept in sync with payload)
    created_at = Column(String(40), nullable=False, index=True)
    updated_at = Column(String(40), nullable=False, index=True)
    status = Column(String(16), nullable=False, index=True, default="new")
    stage = Column(String(16), nullable=False, index=True, default="lead")
    score = Column(Integer, nullable=False, default=1, index=True)
    source = Column(String(32), nullable=False, default="manual", index=True)
    follow_up_due = Column(String(40), nullable=True, index=True)
    converted_at = Column(String(40), nullable=True, index=True)
    value = Column(Float, nullable=False, default=0.0)
    converted_value = Column(Float, nullable=False, default=0.0)


def register_outreach_crm_routes(
    app: Any,
    *,
    base_dir: str,
    require_authenticated_user: Callable[..., Any],
) -> None:
    """
    Register Outreach CRM endpoints on a FastAPI app.

    IMPORTANT:
    - Keep routes, params, and response shapes stable.
    - Do not import `app.py`; pass dependencies in from the orchestrator.
    """

    lead_status_order = {"new", "contacted", "replied", "closed"}
    lead_stage_order = {"lead", "contacted", "replied", "demo", "closed"}

    class LeadAddRequest(BaseModel):
        username: str
        text: str
        source: str | None = "manual"
        value: float | None = None

        @field_validator("username")
        @classmethod
        def validate_username_field(cls, v: str) -> str:
            text = (v or "").strip()
            if not text:
                raise ValueError("username required")
            if len(text) > 120:
                raise ValueError("username too long")
            return text

        @field_validator("text")
        @classmethod
        def validate_text_field(cls, v: str) -> str:
            text = (v or "").strip()
            if not text:
                raise ValueError("text required")
            if len(text) > 5000:
                raise ValueError("text too long")
            return text

        @field_validator("value")
        @classmethod
        def validate_value_field(cls, v: float | None) -> float | None:
            if v is None:
                return None
            try:
                value = float(v)
            except Exception:
                return None
            if not math.isfinite(value):
                return None
            return max(0.0, min(1000000.0, value))

    class LeadStatusRequest(BaseModel):
        status: str | None = None
        stage: str | None = None
        note: str | None = None
        value: float | None = None
        probability: float | None = None

        @field_validator("status")
        @classmethod
        def validate_status_field(cls, v: str | None) -> str | None:
            if v is None:
                return None
            status = (v or "").strip().lower()
            if status not in lead_status_order:
                raise ValueError("status must be one of new/contacted/replied/closed")
            return status

        @field_validator("stage")
        @classmethod
        def validate_stage_field(cls, v: str | None) -> str | None:
            if v is None:
                return None
            stage = (v or "").strip().lower()
            if stage not in lead_stage_order:
                raise ValueError("stage must be one of lead/contacted/replied/demo/closed")
            return stage

        @field_validator("value")
        @classmethod
        def validate_value_field(cls, v: float | None) -> float | None:
            if v is None:
                return None
            try:
                value = float(v)
            except Exception:
                return None
            if not math.isfinite(value):
                return None
            return max(0.0, min(1000000.0, value))

        @field_validator("probability")
        @classmethod
        def validate_probability_field(cls, v: float | None) -> float | None:
            if v is None:
                return None
            try:
                value = float(v)
            except Exception:
                return None
            if not math.isfinite(value):
                return None
            return max(0.0, min(1.0, value))

    class LeadReminderRequest(BaseModel):
        days: int | None = 1
        note: str | None = None

        @field_validator("days")
        @classmethod
        def validate_days_field(cls, v: int | None) -> int:
            try:
                value = int(v or 1)
            except Exception:
                value = 1
            return max(1, min(14, value))

    class LeadConvertRequest(BaseModel):
        value: float | None = 0
        note: str | None = None

        @field_validator("value")
        @classmethod
        def validate_value_field(cls, v: float | None) -> float:
            try:
                value = float(v or 0)
            except Exception:
                value = 0.0
            return max(0.0, min(1000000.0, value))

    def _crm_now() -> datetime:
        return datetime.now(timezone.utc)

    def _crm_now_iso() -> str:
        return _crm_now().isoformat()

    def _infer_lead_source(text: str, source: str | None = None) -> str:
        explicit = str(source or "").strip().lower()
        if explicit and explicit not in {"", "manual", "unknown", "n/a"}:
            if explicit == "x":
                return "twitter"
            return explicit
        lowered = str(text or "").lower()
        if "reddit" in lowered or "r/" in lowered or "subreddit" in lowered:
            return "reddit"
        if "twitter" in lowered or "tweet" in lowered or "x.com" in lowered or " on x " in f" {lowered} ":
            return "twitter"
        if "linkedin" in lowered:
            return "linkedin"
        if "shopify" in lowered:
            return "shopify"
        if "zendesk" in lowered:
            return "zendesk"
        return "manual"

    def _normalize_lead_status(value: str) -> str:
        status = (value or "new").strip().lower()
        return status if status in lead_status_order else "new"

    def _normalize_lead_stage(value: str | None, status: str | None = None) -> str:
        stage = (value or "").strip().lower()
        if stage in lead_stage_order:
            return stage
        status_norm = _normalize_lead_status(status or "new")
        mapping = {"new": "lead", "contacted": "contacted", "replied": "replied", "closed": "closed"}
        return mapping.get(status_norm, "lead")

    def _lead_from_row(row: OutreachLeadRow) -> dict[str, Any] | None:
        try:
            payload = json.loads(str(row.payload_json or "{}"))
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        if not payload:
            return None
        return _serialize_lead(payload)

    def _persist_lead(db, lead: dict[str, Any]) -> dict[str, Any]:
        now_iso = _crm_now_iso()
        normalized = _serialize_lead(lead)
        lead_id = str(normalized.get("id") or "").strip() or uuid.uuid4().hex
        normalized["id"] = lead_id

        row = db.query(OutreachLeadRow).filter(OutreachLeadRow.id == str(lead_id)[:64]).first()
        if row is None:
            row = OutreachLeadRow(id=str(lead_id)[:64])
            db.add(row)

        row.payload_json = json.dumps(normalized, ensure_ascii=False, default=str)
        row.created_at = str(normalized.get("created_at") or now_iso)[:40]
        row.updated_at = now_iso[:40]
        row.status = str(normalized.get("status") or "new")[:16]
        row.stage = str(normalized.get("stage") or "lead")[:16]
        try:
            row.score = int(normalized.get("score", 1) or 1)
        except Exception:
            row.score = 1
        row.source = str(normalized.get("source") or "manual")[:32]
        row.follow_up_due = str(normalized.get("follow_up_due"))[:40] if normalized.get("follow_up_due") else None
        row.converted_at = str(normalized.get("converted_at"))[:40] if normalized.get("converted_at") else None
        try:
            row.value = float(normalized.get("value", 0.0) or 0.0)
        except Exception:
            row.value = 0.0
        try:
            row.converted_value = float(normalized.get("converted_value", 0.0) or 0.0)
        except Exception:
            row.converted_value = 0.0

        return normalized

    def _lead_score(text: str, source: str = "manual") -> int:
        lowered = (text or "").lower()
        score = 0
        keyword_weights = {
            "zendesk": 2,
            "gorgias": 2,
            "support": 1,
            "customer support": 2,
            "tickets": 2,
            "refund": 2,
            "refunds": 2,
            "chargeback": 3,
            "complaint": 2,
            "cancel": 2,
            "shopify": 2,
            "manual": 1,
            "out of control": 3,
            "killing us": 3,
            "painful": 2,
            "swamped": 2,
            "overwhelmed": 2,
        }
        for key, weight in keyword_weights.items():
            if key in lowered:
                score += weight
        if (source or "").lower() in {"reddit", "twitter", "x", "shopify"}:
            score += 1
        return max(score, 1)

    def _generate_initial_lead_message(username: str, text: str) -> str:
        excerpt = " ".join((text or "").strip().split())
        excerpt = excerpt[:140] + ("..." if len(excerpt) > 140 else "")
        return (
            f"Hey — saw your post about support:\n\n"
            f"\"{excerpt}\"\n\n"
            f"I built a tool that prepares support decisions (refunds, replies, escalations) "
            f"but keeps you in control with approval.\n\n"
            f"It usually cuts support workload pretty hard without adding risk.\n\n"
            f"Happy to run a few of your tickets through it for free if you want to see it."
        )

    def _generate_followup_message(lead: dict[str, Any]) -> str:
        text = str(lead.get("text", "") or "").lower()
        if "refund" in text or "charge" in text:
            angle = "Still dealing with refund volume?"
        elif "zendesk" in text or "ticket" in text:
            angle = "Still getting hit by ticket volume?"
        else:
            angle = "Just looping back on this"
        return (
            f"{angle}\n\n"
            f"Happy to show how Xalvion prepares the right support action "
            f"while keeping approval in your hands."
        )

    def _build_lead_record(username: str, text: str, source: str = "manual") -> dict[str, Any]:
        now_iso = _crm_now_iso()
        normalized_source = _infer_lead_source(text, source)
        score = _lead_score(text, normalized_source)
        initial = _generate_initial_lead_message(username, text)
        follow_up_due = (_crm_now() + timedelta(days=2)).isoformat()
        return {
            "id": uuid.uuid4().hex,
            "username": (username or "").strip(),
            "text": (text or "").strip(),
            "source": normalized_source,
            "score": score,
            "status": "new",
            "stage": "lead",
            "value": 0.0,
            "converted_value": 0.0,
            "converted_at": None,
            "created_at": now_iso,
            "last_contacted": None,
            "follow_up_due": follow_up_due,
            "message": initial,
            "follow_up_message": _generate_followup_message({"text": text}),
            "messages": [
                {
                    "type": "initial",
                    "text": initial,
                    "timestamp": now_iso,
                }
            ],
            "notes": [],
        }

    def _serialize_lead(lead: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(lead or {})
        normalized["status"] = _normalize_lead_status(str(normalized.get("status", "new") or "new"))
        normalized["stage"] = _normalize_lead_stage(str(normalized.get("stage", "") or ""), normalized["status"])
        normalized["score"] = int(normalized.get("score", 1) or 1)
        normalized["source"] = _infer_lead_source(
            str(normalized.get("text", "") or ""),
            str(normalized.get("source", "manual") or "manual"),
        )
        normalized["message"] = str(normalized.get("message", "") or "")
        normalized["follow_up_message"] = str(
            normalized.get("follow_up_message") or _generate_followup_message(normalized)
        )
        normalized["messages"] = list(normalized.get("messages") or [])
        normalized["notes"] = list(normalized.get("notes") or [])
        normalized["last_contacted"] = normalized.get("last_contacted")
        normalized["follow_up_due"] = normalized.get("follow_up_due")
        normalized["converted_at"] = normalized.get("converted_at")
        try:
            normalized["value"] = round(float(normalized.get("value", 0) or 0), 2)
        except Exception:
            normalized["value"] = 0.0
        try:
            normalized["converted_value"] = round(float(normalized.get("converted_value", 0) or 0), 2)
        except Exception:
            normalized["converted_value"] = 0.0
        return normalized

    def _crm_day_bucket(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(str(value)).date().isoformat()
        except Exception:
            return ""

    def _is_due_followup(lead: dict[str, Any], now: datetime | None = None) -> bool:
        now = now or _crm_now()
        if (
            _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new"))
            not in {"contacted", "replied", "demo"}
        ):
            return False
        due_at = lead.get("follow_up_due")
        if not due_at:
            return False
        try:
            return datetime.fromisoformat(str(due_at)) <= now
        except Exception:
            return False

    def _lead_hotness(lead: dict[str, Any]) -> int:
        stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new"))
        stage_weight = {"demo": 8, "replied": 6, "contacted": 3, "lead": 1, "closed": -2}.get(stage, 0)
        due_bonus = 2 if _is_due_followup(lead) else 0
        value_bonus = min(4, int(float(lead.get("value", 0) or 0) // 100))
        return int(lead.get("score", 0) or 0) + stage_weight + due_bonus + value_bonus

    def _get_due_reminders(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _crm_now()
        due = [lead for lead in leads if _is_due_followup(lead, now)]
        due.sort(key=lambda lead: (-_lead_hotness(lead), str(lead.get("follow_up_due") or "")))
        return due

    def _get_daily_summary(leads: list[dict[str, Any]]) -> dict[str, Any]:
        today = _crm_now().date().isoformat()
        reminders = _get_due_reminders(leads)
        open_leads = [
            lead for lead in leads if _normalize_lead_status(str(lead.get("status", "new") or "new")) != "closed"
        ]
        hottest = sorted(open_leads, key=lambda lead: (-_lead_hotness(lead), str(lead.get("created_at") or "")))[:3]

        new_today = sum(1 for lead in leads if _crm_day_bucket(lead.get("created_at")) == today)
        contacted_today = sum(1 for lead in leads if _crm_day_bucket(lead.get("last_contacted")) == today)
        closed_today = sum(
            1
            for lead in leads
            if _crm_day_bucket(lead.get("converted_at")) == today
            or (_normalize_lead_status(str(lead.get("status", "new") or "new")) == "closed" and _crm_day_bucket(lead.get("last_contacted")) == today)
        )
        closed_revenue_today = round(
            sum(float(lead.get("converted_value", 0) or 0) for lead in leads if _crm_day_bucket(lead.get("converted_at")) == today),
            2,
        )

        source_counts: dict[str, int] = {}
        for lead in leads:
            source = str(lead.get("source", "manual") or "manual")
            source_counts[source] = source_counts.get(source, 0) + 1
        best_source = "manual"
        if source_counts:
            best_source = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

        return {
            "date": today,
            "due_followups": len(reminders),
            "new_today": new_today,
            "contacted_today": contacted_today,
            "closed_today": closed_today,
            "closed_revenue_today": closed_revenue_today,
            "best_source": best_source,
            "hottest_open": [
                {
                    "id": lead.get("id"),
                    "username": lead.get("username"),
                    "source": lead.get("source"),
                    "status": lead.get("status"),
                    "score": lead.get("score"),
                    "follow_up_due": lead.get("follow_up_due"),
                    "hotness": _lead_hotness(lead),
                }
                for lead in hottest
            ],
            "reminders": [
                {
                    "id": lead.get("id"),
                    "username": lead.get("username"),
                    "status": lead.get("status"),
                    "source": lead.get("source"),
                    "follow_up_due": lead.get("follow_up_due"),
                    "message": str(lead.get("follow_up_message") or lead.get("message") or ""),
                }
                for lead in reminders[:5]
            ],
        }

    def _get_sorted_leads() -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(OutreachLeadRow).all()
            leads: list[dict[str, Any]] = []
            for r in rows:
                lead = _lead_from_row(r)
                if lead:
                    leads.append(lead)
        finally:
            db.close()
        stage_rank = {"demo": 0, "replied": 1, "contacted": 2, "lead": 3, "closed": 4}
        leads.sort(
            key=lambda item: (
                stage_rank.get(item.get("stage", item.get("status", "new")), 9),
                -(int(item.get("score", 0) or 0)),
                item.get("created_at", ""),
            )
        )
        return leads

    def _get_lead_summary(leads: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"new": 0, "contacted": 0, "replied": 0, "closed": 0, "due_followups": 0}
        now = _crm_now()
        for lead in leads:
            status = _normalize_lead_status(str(lead.get("status", "new") or "new"))
            counts[status] = counts.get(status, 0) + 1
            due_at = lead.get("follow_up_due")
            if _is_due_followup(lead, now) and due_at:
                counts["due_followups"] += 1
        return counts

    def _stage_counts(leads: list[dict[str, Any]]) -> dict[str, int]:
        counts = {stage: 0 for stage in lead_stage_order}
        for lead in leads:
            stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), str(lead.get("status", "new") or "new"))
            counts[stage] = counts.get(stage, 0) + 1
        return counts

    def _pct(num: float, den: float) -> float:
        return round((float(num) / float(den) * 100.0), 1) if den else 0.0

    def _compute_revenue_metrics(leads: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = [_serialize_lead(lead) for lead in leads]
        stage_counts = _stage_counts(normalized)
        total = len(normalized)
        contacted_plus = sum(
            1
            for lead in normalized
            if _normalize_lead_stage(lead.get("stage"), lead.get("status"))
            in {"contacted", "replied", "demo", "closed"}
        )
        replied_plus = sum(
            1
            for lead in normalized
            if _normalize_lead_stage(lead.get("stage"), lead.get("status")) in {"replied", "demo", "closed"}
        )
        demos = stage_counts.get("demo", 0)
        closed = stage_counts.get("closed", 0)
        revenue = round(sum(float(lead.get("converted_value", 0) or 0) for lead in normalized), 2)
        open_value = round(
            sum(
                float(lead.get("value", 0) or 0)
                for lead in normalized
                if _normalize_lead_stage(lead.get("stage"), lead.get("status")) != "closed"
            ),
            2,
        )
        by_source_map: dict[str, dict[str, Any]] = {}
        for lead in normalized:
            source = str(lead.get("source", "manual") or "manual")
            stage = _normalize_lead_stage(lead.get("stage"), lead.get("status"))
            bucket = by_source_map.setdefault(
                source,
                {
                    "source": source,
                    "leads": 0,
                    "contacted": 0,
                    "replied": 0,
                    "demo": 0,
                    "closed": 0,
                    "revenue": 0.0,
                },
            )
            bucket["leads"] += 1
            if stage in {"contacted", "replied", "demo", "closed"}:
                bucket["contacted"] += 1
            if stage in {"replied", "demo", "closed"}:
                bucket["replied"] += 1
            if stage in {"demo", "closed"}:
                bucket["demo"] += 1
            if stage == "closed":
                bucket["closed"] += 1
                bucket["revenue"] = round(float(bucket["revenue"]) + float(lead.get("converted_value", 0) or 0), 2)
        by_source = []
        for bucket in by_source_map.values():
            contacted = bucket["contacted"]
            replied = bucket["replied"]
            demo = bucket["demo"]
            closed_count = bucket["closed"]
            leads_count = bucket["leads"]
            bucket["lead_to_contact_rate"] = _pct(contacted, leads_count)
            bucket["reply_rate"] = _pct(replied, contacted)
            bucket["closing_rate"] = _pct(closed_count, leads_count)
            bucket["win_rate"] = _pct(closed_count, demo)
            by_source.append(bucket)
        by_source.sort(
            key=lambda item: (-float(item.get("revenue", 0)), -float(item.get("win_rate", 0)), item.get("source", ""))
        )
        best_source = by_source[0]["source"] if by_source else "manual"
        return {
            "totals": {
                "leads": total,
                "lead": stage_counts.get("lead", 0),
                "contacted": stage_counts.get("contacted", 0),
                "replied": stage_counts.get("replied", 0),
                "demo": stage_counts.get("demo", 0),
                "closed": closed,
                "contacted_or_beyond": contacted_plus,
                "replied_or_beyond": replied_plus,
                "revenue": revenue,
                "open_value": open_value,
                "reply_rate": _pct(replied_plus, contacted_plus),
                "closing_rate": _pct(closed, total),
                "lead_to_close_rate": _pct(closed, total),
                "win_rate": _pct(closed, demos),
            },
            "best_source": best_source,
            "by_source": by_source,
        }

    def _snooze_lead_reminder(lead_id: str, days: int = 1, note: str | None = None) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            row = db.query(OutreachLeadRow).filter(OutreachLeadRow.id == str(lead_id)[:64]).first()
            if not row:
                return None
            lead = _lead_from_row(row) or {}
            now_iso = _crm_now_iso()
            new_due = (_crm_now() + timedelta(days=max(1, min(14, int(days or 1))))).isoformat()
            lead["follow_up_due"] = new_due
            if note:
                notes = list(lead.get("notes") or [])
                notes.append({"text": str(note)[:300], "timestamp": now_iso})
                lead["notes"] = notes[-12:]
            updated_lead = _persist_lead(db, lead)
            db.commit()
            return updated_lead
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _update_lead_status(
        lead_id: str,
        status: str | None = None,
        note: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            row = db.query(OutreachLeadRow).filter(OutreachLeadRow.id == str(lead_id)[:64]).first()
            if not row:
                return None
            lead = _lead_from_row(row) or {}
            now_iso = _crm_now_iso()

            current_status = _normalize_lead_status(str(lead.get("status", "new") or "new"))
            current_stage = _normalize_lead_stage(str(lead.get("stage", "") or ""), current_status)
            new_status = _normalize_lead_status(status or current_status)
            new_stage = _normalize_lead_stage(stage or current_stage, new_status)

            if stage == "lead":
                new_status = "new"
            elif stage == "contacted":
                new_status = "contacted"
            elif stage in {"replied", "demo"}:
                new_status = "replied"
            elif stage == "closed":
                new_status = "closed"

            lead["status"] = new_status
            lead["stage"] = new_stage

            if new_stage == "contacted":
                lead["last_contacted"] = now_iso
                lead["follow_up_due"] = (_crm_now() + timedelta(days=2)).isoformat()
                follow_text = _generate_followup_message(lead)
                lead["follow_up_message"] = follow_text
                history = list(lead.get("messages") or [])
                history.append({"type": "follow_up_scheduled", "text": follow_text, "timestamp": now_iso})
                lead["messages"] = history[-12:]
            elif new_stage == "replied":
                lead["last_contacted"] = now_iso
                lead["follow_up_due"] = (_crm_now() + timedelta(days=3)).isoformat()
            elif new_stage == "demo":
                lead["last_contacted"] = now_iso
                lead["follow_up_due"] = (_crm_now() + timedelta(days=4)).isoformat()
            elif new_stage == "closed":
                lead["follow_up_due"] = None
                lead["converted_at"] = lead.get("converted_at") or now_iso

            if note:
                notes = list(lead.get("notes") or [])
                notes.append({"text": str(note)[:300], "timestamp": now_iso})
                lead["notes"] = notes[-12:]

            updated_lead = _persist_lead(db, lead)
            db.commit()
            return updated_lead
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @app.get("/leads")
    def list_outreach_leads(user=Depends(require_authenticated_user)):  # noqa: ANN001
        leads = _get_sorted_leads()
        return {
            "items": leads,
            "summary": _get_lead_summary(leads),
            "daily_summary": _get_daily_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.get("/leads/followups")
    def list_outreach_followups(user=Depends(require_authenticated_user)):  # noqa: ANN001
        leads = _get_sorted_leads()
        now = _crm_now()
        due: list[dict[str, Any]] = []
        for lead in leads:
            due_at = lead.get("follow_up_due")
            if lead.get("status") != "contacted" or not due_at:
                continue
            try:
                if datetime.fromisoformat(str(due_at)) <= now:
                    due.append(lead)
            except Exception:
                continue
        return {
            "items": due,
            "summary": _get_lead_summary(leads),
            "daily_summary": _get_daily_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.post("/leads/add")
    def add_outreach_lead(req: LeadAddRequest, user=Depends(require_authenticated_user)):  # noqa: ANN001
        record = _build_lead_record(req.username, req.text, req.source or "manual")
        db = SessionLocal()
        try:
            record = _persist_lead(db, record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        all_leads = _get_sorted_leads()
        return {
            "lead": _serialize_lead(record),
            "items": all_leads,
            "summary": _get_lead_summary(all_leads),
            "daily_summary": _get_daily_summary(all_leads),
            "metrics": _compute_revenue_metrics(all_leads),
            "username": getattr(user, "username", ""),
        }

    @app.post("/leads/{lead_id}/status")
    def update_outreach_lead_status(  # noqa: ANN001
        lead_id: str,
        req: LeadStatusRequest,
        user=Depends(require_authenticated_user),
    ):
        updated = _update_lead_status(lead_id, req.status, req.note, req.stage)
        if not updated:
            raise HTTPException(status_code=404, detail="Lead not found")

        all_leads = _get_sorted_leads()
        return {
            "lead": updated,
            "items": all_leads,
            "summary": _get_lead_summary(all_leads),
            "daily_summary": _get_daily_summary(all_leads),
            "metrics": _compute_revenue_metrics(all_leads),
            "username": getattr(user, "username", ""),
        }

    @app.get("/crm/daily-summary")
    def crm_daily_summary(user=Depends(require_authenticated_user)):  # noqa: ANN001
        leads = _get_sorted_leads()
        return {
            "summary": _get_daily_summary(leads),
            "lead_summary": _get_lead_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.get("/crm/reminders")
    def crm_reminders(user=Depends(require_authenticated_user)):  # noqa: ANN001
        leads = _get_sorted_leads()
        return {
            "items": _get_due_reminders(leads),
            "summary": _get_daily_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.post("/crm/reminders/{lead_id}/done")
    def mark_crm_reminder_done(  # noqa: ANN001
        lead_id: str,
        req: LeadReminderRequest,
        user=Depends(require_authenticated_user),
    ):
        updated = _snooze_lead_reminder(lead_id, max(2, req.days), req.note or "Follow-up sent")
        if not updated:
            raise HTTPException(status_code=404, detail="Lead not found")
        leads = _get_sorted_leads()
        return {
            "lead": updated,
            "items": leads,
            "summary": _get_lead_summary(leads),
            "daily_summary": _get_daily_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.post("/crm/reminders/{lead_id}/snooze")
    def snooze_crm_reminder(  # noqa: ANN001
        lead_id: str,
        req: LeadReminderRequest,
        user=Depends(require_authenticated_user),
    ):
        updated = _snooze_lead_reminder(lead_id, req.days, req.note or f"Snoozed {req.days} day")
        if not updated:
            raise HTTPException(status_code=404, detail="Lead not found")
        leads = _get_sorted_leads()
        return {
            "lead": updated,
            "items": leads,
            "summary": _get_lead_summary(leads),
            "daily_summary": _get_daily_summary(leads),
            "metrics": _compute_revenue_metrics(leads),
            "username": getattr(user, "username", ""),
        }

    @app.get("/analytics/metrics")
    def analytics_metrics(user=Depends(require_authenticated_user)):  # noqa: ANN001
        leads = _get_sorted_leads()
        return {
            "metrics": _compute_revenue_metrics(leads),
            "summary": _get_lead_summary(leads),
            "daily_summary": _get_daily_summary(leads),
            "username": getattr(user, "username", ""),
        }

    @app.post("/leads/{lead_id}/convert")
    def convert_outreach_lead(  # noqa: ANN001
        lead_id: str,
        req: LeadConvertRequest,
        user=Depends(require_authenticated_user),
    ):
        db = SessionLocal()
        try:
            row = db.query(OutreachLeadRow).filter(OutreachLeadRow.id == str(lead_id)[:64]).first()
            if not row:
                raise HTTPException(status_code=404, detail="Lead not found")
            lead = _lead_from_row(row) or {}
            now_iso = _crm_now_iso()
            lead["stage"] = "closed"
            lead["status"] = "closed"
            lead["converted_value"] = round(float(req.value or 0), 2)
            lead["value"] = round(max(float(lead.get("value", 0) or 0), float(req.value or 0)), 2)
            lead["converted_at"] = now_iso
            lead["follow_up_due"] = None
            lead["last_contacted"] = now_iso
            if req.note:
                notes = list(lead.get("notes") or [])
                notes.append({"text": str(req.note)[:300], "timestamp": now_iso})
                lead["notes"] = notes[-12:]
            updated = _persist_lead(db, lead)
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        all_leads = _get_sorted_leads()
        return {
            "lead": updated,
            "items": all_leads,
            "summary": _get_lead_summary(all_leads),
            "daily_summary": _get_daily_summary(all_leads),
            "metrics": _compute_revenue_metrics(all_leads),
            "username": getattr(user, "username", ""),
        }

