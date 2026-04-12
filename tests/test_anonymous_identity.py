"""
Anonymous / preview identity: stable guest_client_id must isolate tenants.

Regression: shared literals ``guest`` / ``extension_guest`` must never be used
as the storage principal for tickets, memory, outcomes, or analytics.
"""
from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as app_mod


@pytest.fixture
def client():
    with TestClient(app_mod.app) as c:
        yield c


def test_resolve_storage_principal_accounts_vs_guest():
    from types import SimpleNamespace

    alice = SimpleNamespace(username="alice")
    assert app_mod.resolve_storage_principal(alice, None) == "alice"

    guest = SimpleNamespace(username="guest")
    assert app_mod.resolve_storage_principal(guest, "pytestClientA") == "pytestClientA"

    with pytest.raises(HTTPException):
        app_mod.resolve_storage_principal(guest, None)


def test_two_anonymous_clients_do_not_share_memory():
    from memory import get_user_memory, update_memory

    a = "pytest_mem_isolation_a"
    b = "pytest_mem_isolation_b"
    ticket = {
        "issue": "Isolation probe A",
        "issue_type": "general_support",
        "sentiment": 5,
        "ltv": 0,
        "plan_tier": "free",
    }
    update_memory(a, ticket, "reply-a", {"action": "none", "amount": 0})
    other = get_user_memory(b)
    issues = [str(h.get("issue", "")) for h in other.get("history", [])]
    assert not any("Isolation probe A" in s for s in issues)


def test_guest_ticket_recent_matches_create(client: TestClient):
    """Tickets created under X-Xalvion-Guest-Client must appear only for that client."""
    h1 = {"X-Xalvion-Guest-Client": "pytestTicketOwner01"}
    h2 = {"X-Xalvion-Guest-Client": "pytestTicketOwner02"}
    body = {"message": "My package arrived damaged"}
    r1 = client.post("/support", json=body, headers=h1)
    assert r1.status_code == 200, r1.text
    tid = (r1.json().get("ticket") or {}).get("id")
    assert tid

    recent_ok = client.get("/tickets/recent", headers=h1)
    assert recent_ok.status_code == 200, recent_ok.text
    ids_ok = [x.get("id") for x in recent_ok.json().get("items", [])]
    assert tid in ids_ok

    recent_other = client.get("/tickets/recent", headers=h2)
    assert recent_other.status_code == 200, recent_other.text
    ids_other = [x.get("id") for x in recent_other.json().get("items", [])]
    assert tid not in ids_other
