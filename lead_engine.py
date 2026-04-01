from __future__ import annotations

from datetime import datetime
from typing import Any

from persistence_layer import LeadPayload, LeadRepository

_repo = LeadRepository()


def load_leads() -> list[dict[str, Any]]:
    return _repo.list_all()


def save_leads(leads: list[dict[str, Any]]) -> None:
    _repo.save_all(leads)


def score_lead(text: str) -> int:
    lowered = (text or "").lower()
    score = 0
    keywords = ["support", "refund", "customer service", "zendesk", "tickets", "complaint"]
    for keyword in keywords:
        if keyword in lowered:
            score += 1
    return score


def generate_message(text: str) -> str:
    snippet = (text or "")[:120]
    return f'''Hey - saw your post about support:

"{snippet}..."

I built a tool that prepares support decisions (refunds, replies, etc)
but keeps you in control with approval.

Most people cut support workload by ~60%.

Happy to run a few of your tickets through it if you want to see it.
'''


def add_lead(username: str, text: str, source: str = "manual") -> dict[str, Any]:
    payload = LeadPayload(
        username=username,
        text=text,
        source=source,
        status="new",
        score=score_lead(text),
        message=generate_message(text),
        metadata={"created_by": "lead_engine", "created_at_hint": str(datetime.utcnow())},
    )
    lead = _repo.add(payload)
    print(f"Added lead: {lead['username']} (score={lead['score']})")
    return lead


def list_top_leads(min_score: int = 1) -> list[dict[str, Any]]:
    leads = _repo.list_top(min_score=min_score, status="new")
    for lead in leads:
        print("\n---")
        print(f"User: {lead['username']}")
        print(f"Score: {lead['score']}")
        print(f"Text: {lead['text'][:200]}")
        print("\nSuggested Message:\n")
        print(lead["message"])
    return leads


def _mark_status(username: str, status: str) -> None:
    _repo.update_status(username=username, status=status)


def mark_messaged(username: str) -> None:
    _mark_status(username, "messaged")


def mark_replied(username: str) -> None:
    _mark_status(username, "replied")


def mark_closed(username: str) -> None:
    _mark_status(username, "closed")
