"""
Route tests for ticket approval/rejection, email reply dispatch,
SSE streaming, and growth event/feedback endpoints.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import app as app_mod


@pytest.fixture
def client():
    with TestClient(app_mod.app) as c:
        yield c


def _auth_headers(client: TestClient) -> dict[str, str]:
    user = f"rt_{uuid.uuid4().hex[:12]}"
    password = "secretpass123"
    r = client.post("/signup", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def _parse_sse_lines(lines) -> list[dict]:
    parsed: list[dict] = []
    current_event: str | None = None
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        if not line.strip():
            current_event = None
            continue
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            raw_data = line[5:].strip()
            try:
                payload = json.loads(raw_data)
            except Exception:
                payload = {"raw": raw_data}
            ev_name = current_event or (payload.get("type") if isinstance(payload, dict) else None) or ""
            parsed.append({"event": ev_name, "data": payload})
    return parsed


def test_reply_send_requires_customer_email(client: TestClient):
    h = _auth_headers(client)
    created = client.post("/support", headers=h, json={"message": "Need help with an order"})
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    r = client.post(f"/tickets/{ticket_id}/reply/send", headers=h, json={})
    assert r.status_code == 400


def test_reply_send_dispatches_and_persists_tag(client: TestClient):
    h = _auth_headers(client)
    created = client.post(
        "/support",
        headers=h,
        json={"message": "Need help with an order", "customer_email": "buyer@example.com"},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    fake_send = SimpleNamespace(
        sent=True,
        provider="smtp_test",
        error="",
        message_id="msg_123",
    )
    with patch("routes.support.email_service.send_ticket_reply_email", return_value=fake_send):
        r = client.post(
            f"/tickets/{ticket_id}/reply/send",
            headers=h,
            json={"body": "Your order is being handled."},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("delivery_status") == "sent"
        assert "[email_delivery:sent]" in str((body.get("ticket") or {}).get("internal_note", ""))


def test_reply_send_transport_unavailable_returns_503(client: TestClient):
    h = _auth_headers(client)
    created = client.post(
        "/support",
        headers=h,
        json={"message": "Need help with an order", "customer_email": "buyer@example.com"},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    fake_send = {"status": "transport_unavailable", "message": "SMTP host missing"}
    with patch("routes.support.email_service.send_ticket_reply_email", return_value=fake_send):
        r = client.post(f"/tickets/{ticket_id}/reply/send", headers=h, json={})
        assert r.status_code == 503


def test_approve_pending_refund_executes_and_marks_approved(client: TestClient):
    h = _auth_headers(client)
    created = client.post(
        "/support",
        headers=h,
        json={"message": "I was charged twice on my invoice"},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    db = app_mod.SessionLocal()
    try:
        t_row = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
        if t_row is not None:
            t_row.action = "refund"
            t_row.amount = 25.0
            t_row.requires_approval = 1
            t_row.approved = 0
            t_row.status = "waiting"
            db.commit()
    finally:
        db.close()

    ok_exec = {
        "ok": True,
        "action": "refund",
        "amount": 25.0,
        "tool_status": "refunded",
        "tool_result": {"status": "refunded", "amount": 25.0},
    }
    with patch("execution_boundary.execute_action", return_value=ok_exec):
        r = client.post(f"/tickets/{ticket_id}/approve", headers=h, json={})
        assert r.status_code == 200, r.text
        body = r.json()
        t_payload = body.get("ticket") or body
        log_payload = body.get("action_log") or {}
        approved_val = (
            t_payload.get("approved")
            if "approved" in t_payload
            else log_payload.get("approved", body.get("approved"))
        )
        if approved_val is None:
            db = app_mod.SessionLocal()
            try:
                row = db.query(app_mod.Ticket).filter(app_mod.Ticket.id == ticket_id).first()
                if row is not None:
                    approved_val = row.approved
            finally:
                db.close()
        assert approved_val in {1, True}


def test_approve_execution_failure_returns_409_and_keeps_pending(client: TestClient):
    h = _auth_headers(client)
    created = client.post(
        "/support",
        headers=h,
        json={"message": "I was charged twice on my invoice"},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    failed_exec = {
        "ok": False,
        "tool_status": "failed",
        "tool_result": {"detail": "Stripe refund declined"},
    }
    with patch("execution_boundary.execute_action", return_value=failed_exec):
        r = client.post(f"/tickets/{ticket_id}/approve", headers=h, json={})
        assert r.status_code == 409, r.text

    fetched = client.get(f"/tickets/{ticket_id}", headers=h)
    assert fetched.status_code == 200, fetched.text
    ticket_data = (fetched.json().get("ticket") or fetched.json())
    assert ticket_data.get("requires_approval") in {1, True}
    assert ticket_data.get("approved") in {0, False}


def test_reject_ticket_marks_rejected(client: TestClient):
    h = _auth_headers(client)
    created = client.post(
        "/support",
        headers=h,
        json={"message": "I was charged twice"},
    )
    assert created.status_code == 200, created.text
    ticket_id = (created.json().get("ticket") or {}).get("id")
    assert ticket_id

    r = client.post(f"/tickets/{ticket_id}/reject", headers=h, json={"internal_note": "Not eligible"})
    assert r.status_code == 200, r.text
    body = r.json()
    log_obj = body.get("log") or body.get("action_log") or {}
    log_status = log_obj.get("status")
    if not log_status:
        db = app_mod.SessionLocal()
        try:
            row = (
                db.query(app_mod.ActionLog)
                .filter(app_mod.ActionLog.ticket_id == ticket_id)
                .order_by(app_mod.ActionLog.id.desc())
                .first()
            )
            log_status = row.status if row else None
        finally:
            db.close()
    assert log_status == "rejected"
    assert (body.get("ticket") or {}).get("status") == "escalated"


def test_support_stream_emits_sse_events(client: TestClient):
    h = _auth_headers(client)
    with client.stream(
        "POST",
        "/support/stream",
        headers=h,
        json={"message": "Where is my order?"},
    ) as resp:
        assert resp.status_code == 200
        items = _parse_sse_lines(resp.iter_lines())
        events = [str(item.get("event") or "") for item in items]
        assert "result" in events
        assert "done" in events


def test_support_stream_handles_pipeline_exception_gracefully(client: TestClient):
    h = _auth_headers(client)
    with patch.object(app_mod, "run_support_for_username", side_effect=RuntimeError("boom")):
        with client.stream(
            "POST",
            "/support/stream",
            headers=h,
            json={"message": "Where is my order?"},
        ) as resp:
            assert resp.status_code == 200
            items = _parse_sse_lines(resp.iter_lines())
            events = [str(item.get("event") or "") for item in items]
            assert "result" in events
            assert "done" in events
            done_items = [item for item in items if item.get("event") == "done"]
            assert done_items and (done_items[-1].get("data") or {}).get("ok") is False


def test_growth_event_and_feedback_endpoints(client: TestClient):
    h = _auth_headers(client)
    ev = client.post(
        "/growth/event",
        headers=h,
        json={"type": "workspace_opened", "props": {"source": "pytest", "extra_large": "x" * 500}},
    )
    assert ev.status_code == 200, ev.text
    assert ev.json().get("ok") is True

    fb = client.post(
        "/growth/feedback",
        headers=h,
        json={"rating": "up", "comment": "Helpful flow"},
    )
    assert fb.status_code == 200, fb.text
    assert fb.json().get("ok") is True