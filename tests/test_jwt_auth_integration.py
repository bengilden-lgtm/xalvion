"""
JWT auth integration: login → /me and Stripe state round-trip.

Uses the process ``app`` module (shared metadata/engine). Usernames are UUID
suffixes to avoid collisions with ``aurum.db`` data.
"""
from __future__ import annotations

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


def test_login_then_me_succeeds(client: TestClient):
    user = f"jwt_{uuid.uuid4().hex[:16]}"
    password = "secretpass123"
    r = client.post("/signup", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body.get("token")
    assert token and isinstance(token, str)
    r2 = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, r2.text
    me = r2.json()
    assert me.get("username") == user
    assert me.get("tier") in {"free", "pro", "elite", "dev"}


def test_stripe_state_roundtrip():
    username = f"stripe_{uuid.uuid4().hex[:16]}"
    state = app_mod.create_stripe_state(username)
    assert isinstance(state, str) and state
    assert app_mod.decode_stripe_state(state) == username


def test_create_token_exp_in_future():
    import time

    from jose import jwt as jose_jwt

    before = time.time()
    tok = app_mod.create_token(f"tok_{uuid.uuid4().hex[:12]}")
    payload = jose_jwt.decode(tok, app_mod.SECRET_KEY, algorithms=[app_mod.ALGORITHM])
    exp = int(payload["exp"])
    iat = int(payload["iat"])
    assert exp > iat
    assert exp > int(before)
    assert iat <= int(time.time()) + 2
