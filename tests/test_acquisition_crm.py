"""
Acquisition CRM: approval gates, reply recording, followups.json snapshot.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient

import app as app_mod


@pytest.fixture
def client():
    with TestClient(app_mod.app) as c:
        yield c


def _auth_headers(client: TestClient) -> dict[str, str]:
    user = f"acq_{uuid.uuid4().hex[:12]}"
    password = "secretpass123"
    r = client.post("/signup", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_mark_sent_requires_approval_then_succeeds(client: TestClient):
    h = _auth_headers(client)
    r = client.post(
        "/leads/add",
        headers=h,
        json={"username": "acme_corp", "text": "Zendesk queue is killing us on refunds", "source": "reddit"},
    )
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead"]["id"]

    r2 = client.post(f"/leads/{lead_id}/status", headers=h, json={"status": "contacted"})
    assert r2.status_code == 409, r2.text

    r3 = client.post(f"/leads/{lead_id}/approve-outreach", headers=h, json={})
    assert r3.status_code == 200, r3.text
    assert r3.json()["lead"].get("outreach_message_approved") is True

    r4 = client.post(f"/leads/{lead_id}/status", headers=h, json={"status": "contacted"})
    assert r4.status_code == 200, r4.text
    assert r4.json()["lead"].get("pipeline_stage") == "sent"

    path = os.path.join(app_mod.BASE_DIR, "followups.json")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    ids = [e.get("lead_id") for e in snap.get("entries", [])]
    assert lead_id in ids


def test_record_reply_positive_triggers_booking_push(client: TestClient):
    h = _auth_headers(client)
    r = client.post(
        "/leads/add",
        headers=h,
        json={"username": "warm_lead", "text": "Need to cut ticket volume fast", "source": "manual"},
    )
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead"]["id"]
    client.post(f"/leads/{lead_id}/approve-outreach", headers=h, json={})
    client.post(f"/leads/{lead_id}/status", headers=h, json={"status": "contacted"})

    r2 = client.post(f"/leads/{lead_id}/record-reply", headers=h, json={"reply_text": "Yes — let's schedule something this week."})
    assert r2.status_code == 200, r2.text
    body = r2.json()["lead"]
    assert body.get("replied") is True
    assert body.get("pipeline_stage") == "booked"
    assert body.get("booking_status") == "link_sent"
    assert "cal.com" in str(body.get("follow_up_message", "")).lower() or "http" in str(body.get("follow_up_message", "")).lower()
