from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VALID_MODES = {"conservative", "balanced", "delight", "fraud_aware"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp(value: Any, low: int, high: int, default: int = 0) -> int:
    number = _to_int(value, default)
    if number < low:
        return low
    if number > high:
        return high
    return number


def classify_issue(issue: str) -> str:
    text = (issue or "").lower()

    if "charged twice" in text or "double charge" in text or "billed twice" in text or "duplicate charge" in text:
        return "billing_duplicate_charge"
    if "damaged" in text or "broken" in text:
        return "damaged_order"
    if "refund" in text:
        return "refund_request"
    if "late" in text or "where is my order" in text or "tracking" in text or "package" in text:
        return "shipping_issue"
    if "login" in text or "password" in text or "sign in" in text:
        return "auth_issue"
    if "export" in text and "error" in text:
        return "export_error"

    return "general_support"


def infer_risk_level(ticket: Dict[str, Any], history: Dict[str, Any] | None = None) -> str:
    ticket = ticket or {}
    history = history or {}
    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))

    risk_points = 0
    if issue_type in {"billing_duplicate_charge", "refund_request", "damaged_order"}:
        risk_points += 2
    if sentiment <= 3:
        risk_points += 2
    if ltv >= 800:
        risk_points += 1
    if abuse_score >= 2 or refund_count >= 3:
        risk_points += 2

    if risk_points >= 5:
        return "high"
    if risk_points >= 3:
        return "medium"
    return "low"


def triage_ticket(ticket: Dict[str, Any], history: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ticket = ticket or {}
    history = history or {}
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))
    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    issue_type = str(ticket.get("issue_type", "general_support"))

    urgency = 50
    if sentiment <= 2:
        urgency += 28
    elif sentiment <= 4:
        urgency += 16
    if issue_type in {"billing_duplicate_charge", "damaged_order"}:
        urgency += 18
    elif issue_type == "shipping_issue":
        urgency += 10

    churn_risk = 35
    if sentiment <= 3:
        churn_risk += 25
    if ltv >= 500:
        churn_risk += 20
    if issue_type in {"refund_request", "billing_duplicate_charge"}:
        churn_risk += 10

    refund_likelihood = 10
    if issue_type in {"refund_request", "billing_duplicate_charge"}:
        refund_likelihood += 50
    if issue_type == "damaged_order":
        refund_likelihood += 22
    if sentiment <= 3:
        refund_likelihood += 10

    abuse_likelihood = 5 + min(35, abuse_score * 12) + min(20, refund_count * 5)
    complexity = 25
    if issue_type in {"auth_issue", "export_error"}:
        complexity += 15
    if issue_type in {"refund_request", "billing_duplicate_charge", "damaged_order"}:
        complexity += 20

    urgency = min(99, urgency)
    churn_risk = min(99, churn_risk)
    refund_likelihood = min(99, refund_likelihood)
    abuse_likelihood = min(99, abuse_likelihood)
    complexity = min(99, complexity)

    recommended_owner = "ai"
    if abuse_likelihood >= 50 or complexity >= 70:
        recommended_owner = "senior_operator"
    elif refund_likelihood >= 60:
        recommended_owner = "billing_ops"

    return {
        "urgency": urgency,
        "churn_risk": churn_risk,
        "refund_likelihood": refund_likelihood,
        "abuse_likelihood": abuse_likelihood,
        "complexity": complexity,
        "recommended_owner": recommended_owner,
        "risk_level": infer_risk_level(ticket, history),
    }


def build_ticket(message: str, user_id: str = "anonymous", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = meta or {}
    history = meta.get("customer_history") or {}

    ticket = {
        "customer": user_id,
        "user_id": user_id,
        "issue": (message or "").strip(),
        "ltv": max(0, _to_int(meta.get("ltv", 0), 0)),
        "sentiment": _clamp(meta.get("sentiment", 5), 1, 10, 5),
        "order_status": meta.get("order_status", "unknown"),
        "issue_type": classify_issue(message or ""),
        "plan_tier": str(meta.get("plan_tier", "free") or "free"),
        "operator_mode": str(meta.get("operator_mode", "balanced") or "balanced"),
        "channel": str(meta.get("channel", "web") or "web"),
        "source": str(meta.get("source", "workspace") or "workspace"),
        "customer_history": history,
    }
    ticket["triage"] = triage_ticket(ticket, history)
    return ticket


def _mode_adjust(action: str, amount: int, operator_mode: str, history: Dict[str, Any]) -> tuple[str, int, str | None]:
    operator_mode = (operator_mode or "balanced").strip().lower()
    if operator_mode not in VALID_MODES:
        operator_mode = "balanced"

    abuse_score = max(0, _to_int(history.get("abuse_score", 0), 0))
    refund_count = max(0, _to_int(history.get("refund_count", 0), 0))

    if operator_mode == "conservative":
        if action == "refund":
            return "review", 0, "Conservative mode routed refund for review"
        if action == "credit":
            return "credit", max(5, min(amount, 10)), "Conservative mode reduced automatic credit"

    if operator_mode == "delight":
        if action == "credit":
            return "credit", min(amount + 5, 30), "Delight mode increased retention credit"
        if action == "review":
            return "credit", 10, "Delight mode converted review into service credit"

    if operator_mode == "fraud_aware":
        if abuse_score >= 2 or refund_count >= 3:
            return "review", 0, "Fraud-aware mode detected repeat refund behavior"
        if action == "credit":
            return "credit", max(5, min(amount, 10)), "Fraud-aware mode reduced automatic credit"

    return action, amount, None


def system_decision(ticket: Dict[str, Any]) -> Dict[str, Any]:
    ticket = ticket or {}
    issue = str(ticket.get("issue", "")).lower()
    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    history = ticket.get("customer_history") or {}
    operator_mode = str(ticket.get("operator_mode", "balanced") or "balanced")
    triage = ticket.get("triage") or triage_ticket(ticket, history)

    base = {
        "action": "none",
        "amount": 0,
        "reason": "No hard-rule action triggered",
        "priority": "normal",
        "risk_level": triage.get("risk_level", "low"),
        "queue": "new",
        "requires_approval": False,
    }

    if history.get("abuse_score", 0) >= 3:
        base.update({
            "action": "review",
            "reason": "Repeat abuse signals detected",
            "priority": "high",
            "queue": "refund_risk",
        })
        return base

    if issue_type == "billing_duplicate_charge" or "charged twice" in issue or "double charge" in issue:
        base.update({
            "action": "refund",
            "amount": 25,
            "reason": "Duplicate-charge protection policy",
            "priority": "high",
            "queue": "refund_risk",
            "requires_approval": False,
        })
    elif sentiment <= 2 and ltv >= 500:
        base.update({
            "action": "refund",
            "amount": min(max(int(ltv * 0.10), 20), 50),
            "reason": "High-LTV recovery",
            "priority": "high",
            "queue": "vip",
            "requires_approval": True,
        })
    elif issue_type == "damaged_order" and sentiment <= 4:
        base.update({
            "action": "credit",
            "amount": 20,
            "reason": "Damaged-order recovery",
            "priority": "high",
            "queue": "escalated",
        })
    elif issue_type == "shipping_issue" and sentiment <= 3:
        base.update({
            "action": "credit",
            "amount": 15,
            "reason": "Shipping frustration recovery",
            "priority": "medium",
            "queue": "waiting",
        })
    elif issue_type == "refund_request":
        base.update({
            "action": "review",
            "amount": 0,
            "reason": "Refund request needs context review",
            "priority": "medium",
            "queue": "refund_risk",
        })
    elif triage.get("complexity", 0) >= 70:
        base.update({
            "action": "review",
            "amount": 0,
            "reason": "High-complexity case routed to review",
            "priority": "high",
            "queue": "escalated",
        })

    adjusted_action, adjusted_amount, mode_reason = _mode_adjust(
        str(base.get("action", "none")),
        _to_int(base.get("amount", 0), 0),
        operator_mode,
        history,
    )
    base["action"] = adjusted_action
    base["amount"] = adjusted_amount
    if mode_reason:
        base["reason"] = mode_reason
        if adjusted_action == "review":
            base["queue"] = "refund_risk" if issue_type in {"refund_request", "billing_duplicate_charge"} else "escalated"

    return base


def apply_learned_rules(ticket: Dict[str, Any], learned_rules: List[Dict[str, Any]] | None) -> Dict[str, Any] | None:
    if not learned_rules:
        return None

    issue_type = str(ticket.get("issue_type", "general_support"))
    sentiment = _clamp(ticket.get("sentiment", 5), 1, 10, 5)
    ltv = max(0, _to_int(ticket.get("ltv", 0), 0))
    triage = ticket.get("triage") or {}

    for rule in learned_rules:
        cond = rule.get("condition", {})
        action = rule.get("action", {})

        issue_ok = cond.get("issue_type") in (None, issue_type)
        sentiment_ok = sentiment <= _to_int(cond.get("sentiment_lte", 10), 10)
        ltv_ok = ltv >= _to_int(cond.get("ltv_gte", 0), 0)
        urgency_ok = triage.get("urgency", 0) >= _to_int(cond.get("urgency_gte", 0), 0)

        if issue_ok and sentiment_ok and ltv_ok and urgency_ok:
            chosen_action = str(action.get("type", "none") or "none")
            chosen_amount = _to_int(action.get("amount", 0), 0)
            adjusted_action, adjusted_amount, mode_reason = _mode_adjust(
                chosen_action,
                chosen_amount,
                str(ticket.get("operator_mode", "balanced") or "balanced"),
                ticket.get("customer_history") or {},
            )
            return {
                "action": adjusted_action,
                "amount": adjusted_amount,
                "reason": mode_reason or f"Learned rule: {rule.get('trigger', 'unknown_rule')}",
                "priority": "medium",
                "risk_level": triage.get("risk_level", "medium"),
                "queue": "waiting",
                "requires_approval": adjusted_action == "refund" and adjusted_amount >= 25,
            }

    return None


def calculate_impact(ticket: Dict[str, Any], executed_action: Dict[str, Any]) -> Dict[str, Any]:
    ticket = ticket or {}
    executed_action = executed_action or {}
    action = str(executed_action.get("action", "none") or "none")
    amount = _to_int(executed_action.get("amount", 0), 0)
    triage = ticket.get("triage") or {}

    if action == "refund":
        return {"type": "refund", "amount": amount, "money_saved": 0, "auto_resolved": True}
    if action == "credit":
        recovered = max(10, min(60, amount + 15))
        return {"type": "credit", "amount": amount, "money_saved": recovered, "auto_resolved": True}
    if action == "review":
        return {"type": "saved", "amount": 15, "money_saved": 15, "auto_resolved": False}

    saved = 25
    if triage.get("abuse_likelihood", 0) >= 50:
        saved = 40
    return {"type": "saved", "amount": saved, "money_saved": saved, "auto_resolved": True}

# ===== ACTION EXECUTION LAYER (NO DOWNGRADE) =====

def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None, timeout: float = 12.0) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    merged_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        merged_headers.update({k: str(v) for k, v in headers.items() if v is not None})
    req = Request(url, data=body, headers=merged_headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw.strip():
                return {"ok": True, "status_code": getattr(resp, "status", 200)}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    parsed.setdefault("status_code", getattr(resp, "status", 200))
                    return parsed
            except Exception:
                pass
            return {"ok": True, "status_code": getattr(resp, "status", 200), "raw": raw}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
        return {"ok": False, "status": "http_error", "status_code": exc.code, "detail": detail}
    except URLError as exc:
        return {"ok": False, "status": "network_error", "detail": str(exc)}


def _clean_email(value: Any) -> str:
    text = str(value or "").strip()
    return text if "@" in text and "." in text else ""


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _send_email_via_smtp(*, to_email: str, subject: str, body_text: str, body_html: str | None = None) -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return {"ok": False, "status": "smtp_not_configured", "detail": "SMTP_HOST not configured"}

    port = int(os.getenv("SMTP_PORT", "587") or 587)
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", username).strip()
    from_name = os.getenv("SMTP_FROM_NAME", "Xalvion Support").strip() or "Xalvion Support"
    use_tls = _bool_env("SMTP_USE_TLS", True)
    use_ssl = _bool_env("SMTP_USE_SSL", False)

    if not from_email:
        return {"ok": False, "status": "smtp_missing_from", "detail": "SMTP_FROM_EMAIL or SMTP_USERNAME required"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=12) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as server:
                server.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return {"ok": True, "status": "sent", "provider": "smtp", "to": to_email, "subject": subject}
    except Exception as exc:
        return {"ok": False, "status": "smtp_error", "provider": "smtp", "detail": str(exc)}


def _send_email_via_webhook(*, to_email: str, subject: str, body_text: str, body_html: str | None = None) -> Dict[str, Any]:
    webhook = os.getenv("EMAIL_WEBHOOK_URL", "").strip()
    if not webhook:
        return {"ok": False, "status": "webhook_not_configured", "detail": "EMAIL_WEBHOOK_URL not configured"}

    token = os.getenv("EMAIL_WEBHOOK_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"to": to_email, "subject": subject, "text": body_text, "html": body_html or ""}
    result = _post_json(webhook, payload, headers=headers)
    if result.get("ok") is False:
        return {"ok": False, "status": result.get("status", "webhook_error"), "detail": result.get("detail", "Email webhook failed")}
    return {"ok": True, "status": "sent", "provider": "webhook", "to": to_email, "subject": subject, "response": result}


def send_support_email(*, to_email: str, subject: str, body_text: str, body_html: str | None = None) -> Dict[str, Any]:
    cleaned_to = _clean_email(to_email)
    if not cleaned_to:
        return {"ok": False, "status": "missing_recipient", "detail": "No valid customer email available"}

    provider = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
    if provider == "webhook":
        return _send_email_via_webhook(to_email=cleaned_to, subject=subject, body_text=body_text, body_html=body_html)
    return _send_email_via_smtp(to_email=cleaned_to, subject=subject, body_text=body_text, body_html=body_html)


def resolve_tracking_details(payload: Dict[str, Any]) -> Dict[str, Any]:
    details = {
        "tracking_id": str(payload.get("tracking_id") or payload.get("tracking") or "").strip(),
        "tracking_url": str(payload.get("tracking_url") or "").strip(),
        "status": str(payload.get("status") or payload.get("order_status") or "unknown").strip().lower(),
        "eta": str(payload.get("eta") or "").strip(),
        "carrier": str(payload.get("carrier") or "").strip(),
    }

    lookup_url = os.getenv("TRACKING_LOOKUP_WEBHOOK_URL", "").strip()
    if lookup_url:
        token = os.getenv("TRACKING_LOOKUP_TOKEN", "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        lookup_payload = {
            "customer": payload.get("customer"),
            "customer_email": payload.get("customer_email"),
            "message": payload.get("message"),
            "order_id": payload.get("order_id"),
            "tracking_id": details["tracking_id"],
            "status": details["status"],
        }
        remote = _post_json(lookup_url, lookup_payload, headers=headers)
        if remote.get("ok") is not False:
            details["tracking_id"] = str(remote.get("tracking_id") or remote.get("tracking") or details["tracking_id"]).strip()
            details["tracking_url"] = str(remote.get("tracking_url") or details["tracking_url"]).strip()
            details["status"] = str(remote.get("status") or details["status"] or "unknown").strip().lower()
            details["eta"] = str(remote.get("eta") or details["eta"]).strip()
            details["carrier"] = str(remote.get("carrier") or details["carrier"]).strip()
            details["lookup_response"] = remote

    if not details["tracking_id"]:
        details["tracking_id"] = "TRK-UNAVAILABLE"
    if not details["eta"]:
        details["eta"] = "ETA unavailable"
    return details


def _build_tracking_email_payload(payload: Dict[str, Any], details: Dict[str, Any]) -> tuple[str, str, str]:
    customer_name = str(payload.get("customer_name") or payload.get("customer") or "there").strip() or "there"
    status = details.get("status", "unknown")
    tracking_id = details.get("tracking_id", "TRK-UNAVAILABLE")
    eta = details.get("eta", "ETA unavailable")
    tracking_url = details.get("tracking_url", "").strip()

    subject = "Your order tracking update"
    if status == "delayed":
        subject = "Your order is delayed in transit"
    elif status == "delivered":
        subject = "Your order shows as delivered"
    elif status == "processing":
        subject = "Your order is still processing"

    link_line = tracking_url or tracking_id
    text = (
        f"Hi {customer_name},\n\n"
        f"I checked the latest shipping status for your order.\n\n"
        f"Tracking: {tracking_id}\n"
        f"Status: {status}\n"
        f"Estimated delivery: {eta}\n"
        f"Track here: {link_line}\n\n"
        "If anything looks off, reply to this email and we’ll take care of it.\n\n"
        "Best,\nXalvion Support"
    )
    html = (
        f"<p>Hi {customer_name},</p>"
        f"<p>I checked the latest shipping status for your order.</p>"
        f"<p><strong>Tracking:</strong> {tracking_id}<br>"
        f"<strong>Status:</strong> {status}<br>"
        f"<strong>Estimated delivery:</strong> {eta}</p>"
        f"<p><a href="{tracking_url or '#'}">Track your order</a></p>"
        f"<p>If anything looks off, reply to this email and we’ll take care of it.</p>"
        f"<p>Best,<br>Xalvion Support</p>"
    )
    return subject, text, html


def execute_action(action_type, payload):
    try:
        normalized = str(action_type or "noop").strip().lower()

        if normalized == "refund":
            return handle_refund(payload)
        if normalized == "credit":
            return handle_credit(payload)
        if normalized == "send_tracking":
            return handle_tracking(payload)
        if normalized == "escalate":
            return handle_escalation(payload)
        if normalized == "charge":
            return handle_charge(payload)
        if normalized in {"none", "noop"}:
            return {"status": "no_action", "type": "noop", "message": "No external action executed"}

        return {"status": "unknown_action", "type": normalized, "action": normalized, "message": f"Unknown action: {normalized}"}
    except Exception as e:
        return {"status": "error", "error": str(e), "type": str(action_type or "unknown")}


def handle_refund(payload):
    return {"status": "success", "type": "refund", "amount": payload.get("amount", "unknown"), "message": "Refund prepared", "provider": "workspace_refund_flow"}


def handle_credit(payload):
    return {"status": "success", "type": "credit", "amount": payload.get("amount", 0), "message": "Credit prepared", "provider": "workspace_credit_flow"}


def handle_charge(payload):
    return {"status": "success", "type": "charge", "amount": payload.get("amount", 0), "message": "Charge queued for billing execution", "provider": "workspace_charge_flow"}


def handle_tracking(payload):
    details = resolve_tracking_details(payload)
    subject, body_text, body_html = _build_tracking_email_payload(payload, details)
    customer_email = _clean_email(payload.get("customer_email"))

    email_result = {"ok": False, "status": "missing_recipient", "detail": "No valid customer email available"}
    if customer_email:
        email_result = send_support_email(to_email=customer_email, subject=subject, body_text=body_text, body_html=body_html)

    email_sent = bool(email_result.get("ok"))
    message = "Tracking sent to customer via email" if email_sent else "Tracking prepared but email not sent"

    return {
        "status": "success" if email_sent or details.get("tracking_id") else "partial",
        "type": "tracking",
        "tracking_id": details.get("tracking_id", "TRK-UNAVAILABLE"),
        "tracking_url": details.get("tracking_url", ""),
        "carrier": details.get("carrier", ""),
        "eta": details.get("eta", "ETA unavailable"),
        "shipment_status": details.get("status", "unknown"),
        "message": message,
        "email": email_result,
        "customer_email": customer_email,
        "lookup_response": details.get("lookup_response"),
    }


def handle_escalation(payload):
    webhook = os.getenv("ESCALATION_WEBHOOK_URL", "").strip()
    priority = str(payload.get("priority", "normal") or "normal")
    escalation_payload = {
        "customer": payload.get("customer"),
        "customer_email": payload.get("customer_email"),
        "issue": payload.get("message"),
        "priority": priority,
        "issue_type": payload.get("issue_type"),
        "source": payload.get("source", "workspace"),
    }

    webhook_result = None
    if webhook:
        token = os.getenv("ESCALATION_WEBHOOK_TOKEN", "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        webhook_result = _post_json(webhook, escalation_payload, headers=headers)

    return {
        "status": "success",
        "type": "escalation",
        "priority": priority,
        "message": "Case escalated",
        "webhook": webhook_result,
    }
