"""
Billing/Stripe hardening tests.
"""

from __future__ import annotations

import os
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import app as app_mod
from services import stripe_service


@pytest.fixture
def client():
    with TestClient(app_mod.app) as c:
        yield c


def _db():
    return app_mod.SessionLocal()


def _create_user(db, *, username: str, tier: str = "free", sub_id: str | None = None, sub_status: str | None = None):
    u = app_mod.User(username=username, password="x", usage=0, tier=tier)
    if sub_id is not None:
        u.stripe_subscription_id = sub_id
    if sub_status is not None and hasattr(u, "stripe_subscription_status"):
        u.stripe_subscription_status = sub_status
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth_headers(client: TestClient, *, username: str, password: str) -> dict[str, str]:
    r = client.post("/signup", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json().get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_happy_path_upgrade():
    db = _db()
    try:
        username = f"u_{uuid.uuid4().hex[:12]}"
        _create_user(db, username=username, tier="free")
        result = stripe_service.apply_successful_upgrade(
            db, username, "pro", stripe_subscription_id="sub_123"
        )
        assert result["ok"] is True
        assert result["result"] == "upgraded"
        user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert user.tier == "pro"
        assert user.stripe_subscription_status == "active"
        assert user.stripe_tier_source == "webhook"
        assert user.stripe_subscription_id == "sub_123"
    finally:
        db.close()


def test_idempotent_upgrade_already_on_tier():
    db = _db()
    try:
        username = f"u_{uuid.uuid4().hex[:12]}"
        user = _create_user(db, username=username, tier="pro", sub_id="sub_123", sub_status="active")
        orig = (user.tier, user.stripe_subscription_id, getattr(user, "stripe_subscription_status", None), getattr(user, "stripe_tier_source", None))

        commit_mock = MagicMock()
        db.commit = commit_mock  # type: ignore[assignment]

        result = stripe_service.apply_successful_upgrade(
            db, username, "pro", stripe_subscription_id="sub_123"
        )
        assert result["ok"] is True
        assert result["result"] == "already_on_tier"
        assert commit_mock.call_count == 0

        fresh = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        now = (fresh.tier, fresh.stripe_subscription_id, getattr(fresh, "stripe_subscription_status", None), getattr(fresh, "stripe_tier_source", None))
        assert now == orig
    finally:
        db.close()


def test_webhook_retry_safety_duplicate_event_does_not_reapply_upgrade(client: TestClient):
    db = _db()
    try:
        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        db.add(app_mod.ProcessedWebhook(
            event_id=event_id,
            event_type="checkout.session.completed",
            processed_at=app_mod._now_iso(),
            outcome="completed",
            detail="",
        ))
        db.commit()

        fake_session = SimpleNamespace(
            id="cs_test",
            client_reference_id="someone",
            metadata={"username": "someone", "tier": "pro"},
            subscription="sub_123",
        )
        fake_event = SimpleNamespace(
            id=event_id,
            type="checkout.session.completed",
            data=SimpleNamespace(object=fake_session),
        )

        with (
            patch.object(app_mod, "STRIPE_KEY", "sk_test_123"),
            patch.object(app_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test"),
            patch("stripe.Webhook.construct_event", return_value=fake_event),
            patch("services.stripe_service.apply_successful_upgrade") as upgrade_mock,
        ):
            r = client.post("/stripe/webhook", data=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("duplicate") is True
            assert upgrade_mock.call_count == 0
    finally:
        db.close()


def test_subscription_cancellation_downgrades_and_sets_status():
    db = _db()
    try:
        username = f"u_{uuid.uuid4().hex[:12]}"
        _create_user(db, username=username, tier="pro", sub_id="sub_abc", sub_status="active")
        sub = SimpleNamespace(id="sub_abc", metadata={"username": username})
        outcome, detail = stripe_service.apply_subscription_deleted(db, sub)
        assert outcome == "ok"
        assert "sub_abc" in detail
        user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert user.tier == "free"
        assert user.stripe_subscription_status == "canceled"
    finally:
        db.close()


def test_cancellation_of_wrong_subscription_is_skipped():
    db = _db()
    try:
        username = f"u_{uuid.uuid4().hex[:12]}"
        _create_user(db, username=username, tier="pro", sub_id="sub_new_456")
        sub = SimpleNamespace(id="sub_old_123", metadata={"username": username})
        outcome, detail = stripe_service.apply_subscription_deleted(db, sub)
        assert outcome == "skipped"
        assert "sub_old_123" in detail
        user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert user.tier == "pro"
    finally:
        db.close()


def test_ghost_state_recovery_applies_upgrade_and_marks_completed(client: TestClient):
    username = f"u_{uuid.uuid4().hex[:12]}"
    password = "secretpass123"
    headers = _auth_headers(client, username=username, password=password)

    db = _db()
    try:
        db_user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert db_user is not None
        session_id = f"cs_{uuid.uuid4().hex[:12]}"
        db.add(app_mod.PendingCheckout(
            session_id=session_id,
            username=username,
            tier="pro",
            created_at=app_mod._now_iso(),
            status="pending",
        ))
        db.commit()
    finally:
        db.close()

    fake_retrieve = SimpleNamespace(
        payment_status="paid",
        status="complete",
        metadata={"username": username, "tier": "pro"},
        subscription="sub_999",
    )

    with (
        patch.object(app_mod, "STRIPE_KEY", "sk_test_123"),
        patch("stripe.checkout.Session.retrieve", return_value=fake_retrieve),
    ):
        r = client.post("/billing/recover", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("result") == "recovered"

    db = _db()
    try:
        user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert user.tier == "pro"
        pending = db.query(app_mod.PendingCheckout).filter(app_mod.PendingCheckout.session_id == session_id).first()
        assert pending.status == "completed"
    finally:
        db.close()


def test_past_due_subscription_does_not_lose_access():
    db = _db()
    try:
        username = f"u_{uuid.uuid4().hex[:12]}"
        _create_user(db, username=username, tier="pro", sub_id="sub_777", sub_status="active")
        sub = SimpleNamespace(
            id="sub_777",
            status="past_due",
            metadata={"username": username},
        )
        outcome, detail = stripe_service.apply_subscription_updated(db, sub)
        assert outcome == "payment_issue"
        assert "past_due" in detail
        user = db.query(app_mod.User).filter(app_mod.User.username == username).first()
        assert user.tier == "pro"
        assert user.stripe_subscription_status == "past_due"
        access = stripe_service.validate_plan_access(user)
        assert access["valid"] is True
        assert access["warning"] == "payment_due"
    finally:
        db.close()


def test_price_id_validation_blocks_bad_config(client: TestClient, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_...")
    monkeypatch.setenv("STRIPE_PRICE_ELITE", "price_valid_123456789")
    app_mod.validate_stripe_config()
    assert app_mod.BILLING_ENABLED is False

    username = f"u_{uuid.uuid4().hex[:12]}"
    password = "secretpass123"
    headers = _auth_headers(client, username=username, password=password)

    r = client.post("/billing/upgrade", json={"tier": "pro"}, headers=headers)
    assert r.status_code == 503
