"""
Revenue acquisition helpers: scoring, follow-up suggestions, booking copy, followups.json sync.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any

PIPELINE_STAGES = frozenset({"found", "approved", "sent", "replied", "booked"})
BOOKING_STATUS = frozenset({"none", "link_sent", "confirmed"})


def default_acquisition_config() -> dict[str, Any]:
    return {
        "booking_url": "https://cal.com/example/10min",
        "no_reply_followup_hours": 48,
        "require_outreach_approval": True,
        "require_followup_approval": True,
        "warm_intent_threshold": 55,
    }


def load_acquisition_config(base_dir: str) -> dict[str, Any]:
    cfg = default_acquisition_config()
    path = os.path.join(base_dir, "crm_acquisition_config.json")
    if not os.path.isfile(path):
        try:
            with open(path, "w", encoding="utf-8") as wf:
                json.dump(cfg, wf, indent=2, ensure_ascii=False)
        except OSError:
            pass
        return cfg
    try:
        with open(path, encoding="utf-8") as rf:
            merged = json.load(rf)
        if isinstance(merged, dict):
            cfg.update(merged)
    except Exception:
        pass
    return cfg


def channel_key_for_source(source: str) -> str:
    return _channel_bucket(source)


def _channel_bucket(source: str) -> str:
    s = (source or "manual").lower().strip()
    if s in {"x", "twitter"}:
        return "twitter"
    if s in {"reddit", "linkedin", "shopify", "zendesk", "manual"}:
        return s
    return "manual"


def outcome_message_variants(username: str, text: str, source: str) -> dict[str, list[str]]:
    """Outcome-first outreach lines; never mention 'AI tool'."""
    excerpt = " ".join((text or "").strip().split())
    excerpt = excerpt[:130] + ("..." if len(excerpt) > 130 else "")
    u = (username or "").strip() or "there"

    base_variants = [
        (
            f"Hey {u} — re your support load (\"{excerpt}\"): teams that wire this cut live ticket volume ~40–50% in week one "
            f"without adding risk (everything ships with your approval).\n\n"
            f"Worth trying this on one ticket batch?"
        ),
        (
            f"{u} — saw the pain in: \"{excerpt}\".\n\n"
            f"We fix the support workflow bottleneck in about 7 days — free setup, pay only if it works.\n\n"
            f"I can run this on your tickets for free if you want proof on real volume."
        ),
        (
            f"On \"{excerpt}\": we shorten refund/reply/escalation loops so agents close the right outcome faster.\n\n"
            f"Happy to pilot on a small slice of your queue — 10 minutes to see if it matches how you work."
        ),
        (
            f"{u} — \"{excerpt}\" reads like throughput is the issue.\n\n"
            f"We reduce ticket load by tightening decisions (you stay in control).\n\n"
            f"Open to a no-cost pass on 5–10 tickets?"
        ),
        (
            f"Quick one on \"{excerpt}\": same-week reduction in back-and-forth is the usual outcome.\n\n"
            f"If you want, I’ll mirror your rules on a batch so you can compare before committing."
        ),
    ]

    zendesk_extra = [
        (
            f"{u} — Zendesk-heavy teams use this to cut reopen rate and time-to-resolution on \"{excerpt}\".\n\n"
            f"Want a free batch on live tickets to validate?"
        ),
    ]

    reddit_extra = [
        (
            f"{u} — for threads like \"{excerpt}\", we focus on cutting handle time without changing your tone.\n\n"
            f"Try it on one batch?"
        ),
    ]

    out: dict[str, list[str]] = {
        "manual": list(base_variants),
        "twitter": list(base_variants),
        "linkedin": list(base_variants),
        "shopify": list(base_variants),
        "zendesk": list(base_variants) + zendesk_extra,
        "reddit": list(base_variants) + reddit_extra,
    }
    for k in list(out.keys()):
        out[k] = out[k][:5]
    return out


def pick_ab_variant_index(lead_id: str, variant_count: int) -> int:
    if variant_count <= 0:
        return 0
    h = int(hashlib.sha256(str(lead_id).encode("utf-8")).hexdigest(), 16)
    return h % variant_count


def classify_reply(reply_text: str) -> str:
    t = (reply_text or "").strip().lower()
    if not t:
        return "empty"
    positive = re.search(
        r"\b(yes|yeah|yep|sure|sounds good|let'?s do|schedule|book|call me|demo|interested|love to|i'm in|im in)\b",
        t,
    )
    vague = len(t.split()) <= 6 or t in {"ok", "k", "maybe", "hm", "hmm", "?", "thanks", "thank you", "hi", "hey"}
    if positive:
        return "positive"
    if vague:
        return "vague"
    return "neutral"


def is_lead_warm(lead: dict[str, Any], config: dict[str, Any]) -> bool:
    if classify_reply(str(lead.get("reply_text") or "")) == "positive":
        return True
    thr = float(config.get("warm_intent_threshold", 55) or 55)
    return float(lead.get("intent_score", 0) or 0) >= thr


def suggest_followup_text(lead: dict[str, Any], config: dict[str, Any], now: datetime) -> str | None:
    """Rules: no reply after X hours → nudge; vague → clarify; positive → booking hint (still needs approval)."""
    replied = bool(lead.get("replied"))
    last_sent = lead.get("last_sent_at") or lead.get("last_contacted")
    hours = float(config.get("no_reply_followup_hours", 48) or 48)
    reply_cls = classify_reply(str(lead.get("reply_text") or ""))

    if not replied and last_sent:
        try:
            sent_at = datetime.fromisoformat(str(last_sent))
            if (now - sent_at).total_seconds() >= hours * 3600:
                return (
                    "Circling back — worth trying this on one ticket batch so you can see handle time drop "
                    "without changing how your team works?"
                )
        except Exception:
            pass

    if replied and reply_cls == "vague":
        return (
            "Thanks — quick clarify: is the main pain volume, refunds, or escalations?\n\n"
            "Once I know that, I’ll point the next message at the exact outcome you care about."
        )

    if replied and reply_cls == "positive":
        return (
            "Love it. Easiest next step: I can run this on your tickets for free on a small batch — "
            "you compare before any commitment.\n\n"
            "Want me to start with 5–10 live threads?"
        )

    if replied and reply_cls == "neutral":
        return (
            "Got it. If throughput is still the issue, want a 10‑minute pass on a handful of tickets "
            "so you can see the workflow change end‑to‑end?"
        )
    return None


def suggest_booking_message(booking_url: str) -> str:
    url = (booking_url or "").strip() or "https://cal.com/your-handle/10min"
    return (
        f"Let’s test it on your tickets — takes ~10 mins. Pick a slot here: {url}\n\n"
        f"If none of those work, reply with two windows that fit and I’ll adapt."
    )


def compute_intent_score(lead: dict[str, Any]) -> float:
    try:
        raw = int(lead.get("score", 1) or 1)
    except Exception:
        raw = 1
    return float(min(100, max(0, raw * 8)))


def compute_conversion_score(lead: dict[str, Any]) -> float:
    intent = float(lead.get("intent_score", 0) or 0)
    replied = 28.0 if lead.get("replied") else 0.0
    try:
        fc = int(lead.get("followup_count", 0) or 0)
    except Exception:
        fc = 0
    follow_part = float(min(18, fc * 4))
    try:
        eng = min(16, len(list(lead.get("messages") or [])) * 2)
    except Exception:
        eng = 0.0
    booked = 12.0 if str(lead.get("booking_status") or "none") != "none" else 0.0
    hp = 6.0 if lead.get("high_priority") else 0.0
    total = intent * 0.38 + replied + follow_part + eng + booked + hp
    return float(round(min(100.0, max(0.0, total)), 2))


def merge_acquisition_defaults(
    lead: dict[str, Any],
    *,
    config: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Ensure acquisition fields exist on a lead dict (mutates copy)."""
    out = dict(lead or {})
    ch = channel_key_for_source(str(out.get("source") or "manual"))

    if "pipeline_stage" not in out or not str(out.get("pipeline_stage") or "").strip():
        st = str(out.get("status", "new") or "new").lower()
        if st == "contacted":
            out["pipeline_stage"] = "sent"
        elif st == "replied":
            out["pipeline_stage"] = "replied"
        elif st == "closed":
            out["pipeline_stage"] = "found"
        else:
            out["pipeline_stage"] = "found"

    out.setdefault("last_action_time", out.get("created_at") or now_iso)
    out.setdefault("replied", False)
    out.setdefault("reply_text", None)
    out.setdefault("reply_time", None)
    out.setdefault("followup_count", 0)
    out.setdefault("last_followup_time", None)
    out.setdefault("booking_status", "none")
    out.setdefault("high_priority", False)
    out.setdefault("outreach_message_approved", False)
    out.setdefault("followup_message_approved", False)
    out.setdefault("pending_followup_suggestion", None)
    out.setdefault("pending_booking_message", None)
    out.setdefault("ab_variant_index", 0)
    out.setdefault("ab_variant_channel", ch)
    out.setdefault("last_sent_at", out.get("last_contacted"))

    if "message_variants" not in out or not isinstance(out.get("message_variants"), dict):
        variants_map = outcome_message_variants(str(out.get("username", "")), str(out.get("text", "")), ch)
        out["message_variants"] = variants_map
        keys = list(variants_map.get(ch) or variants_map.get("manual") or [])
        idx = pick_ab_variant_index(str(out.get("id", "")), len(keys))
        out["ab_variant_index"] = idx
        out["ab_variant_channel"] = ch
        if keys:
            out["message"] = keys[idx]
            hist = list(out.get("messages") or [])
            if hist and str(hist[0].get("type")) == "initial":
                hist[0] = {
                    **hist[0],
                    "text": out["message"],
                    "timestamp": hist[0].get("timestamp") or now_iso,
                }
                out["messages"] = hist
            elif not hist:
                out["messages"] = [{"type": "initial", "text": out["message"], "timestamp": now_iso}]

    if str(out.get("pipeline_stage") or "") in {"sent", "replied", "booked"}:
        out.setdefault("outreach_message_approved", True)

    out["intent_score"] = compute_intent_score(out)
    out["conversion_score"] = compute_conversion_score(out)
    msgs = list(out.get("messages") or [])
    out["message_history"] = msgs
    return out


def lead_to_followup_entry(lead: dict[str, Any], *, now_iso: str) -> dict[str, Any]:
    """Shape for followups.json entries."""
    msgs = list(lead.get("messages") or [])
    return {
        "lead_id": lead.get("id"),
        "source": lead.get("source"),
        "message_history": msgs,
        "replied": bool(lead.get("replied")),
        "reply_text": lead.get("reply_text"),
        "reply_time": lead.get("reply_time"),
        "followup_count": int(lead.get("followup_count", 0) or 0),
        "last_followup_time": lead.get("last_followup_time"),
        "pipeline_stage": lead.get("pipeline_stage"),
        "booking_status": lead.get("booking_status"),
        "last_action_time": lead.get("last_action_time"),
        "conversion_score": lead.get("conversion_score"),
        "intent_score": lead.get("intent_score"),
        "high_priority": bool(lead.get("high_priority")),
        "pending_followup_suggestion": lead.get("pending_followup_suggestion"),
        "pending_booking_message": lead.get("pending_booking_message"),
        "follow_up_message": lead.get("follow_up_message"),
        "timestamps": {
            "created_at": lead.get("created_at"),
            "updated_at": now_iso,
            "last_sent_at": lead.get("last_sent_at"),
            "reply_time": lead.get("reply_time"),
            "last_followup_time": lead.get("last_followup_time"),
        },
    }


def write_followups_json(base_dir: str, leads: list[dict[str, Any]], *, now_iso: str) -> None:
    path = os.path.join(base_dir, "followups.json")
    payload = {
        "updated_at": now_iso,
        "entries": [lead_to_followup_entry(lead, now_iso=now_iso) for lead in leads],
    }
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as wf:
            json.dump(payload, wf, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    except OSError:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass


def refresh_followup_suggestion(
    lead: dict[str, Any],
    config: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Recompute pending_followup_suggestion from rules; does not approve or send."""
    lead = dict(lead)
    sug = suggest_followup_text(lead, config, now)
    lead["pending_followup_suggestion"] = sug
    if sug:
        lead["follow_up_message"] = sug
    lead["last_action_time"] = now.replace(tzinfo=timezone.utc).isoformat()
    return lead


def apply_booking_push(
    lead: dict[str, Any],
    config: dict[str, Any],
    *,
    now_iso: str,
) -> dict[str, Any] | None:
    if not is_lead_warm(lead, config):
        return None
    lead = dict(lead)
    msg = suggest_booking_message(str(config.get("booking_url") or ""))
    lead["pending_booking_message"] = msg
    lead["follow_up_message"] = msg
    lead["pipeline_stage"] = "booked"
    lead["booking_status"] = "link_sent"
    lead["last_action_time"] = now_iso
    lead["high_priority"] = True
    hist = list(lead.get("messages") or [])
    hist.append({"type": "booking_suggested", "text": msg, "timestamp": now_iso})
    lead["messages"] = hist[-24:]
    return lead
