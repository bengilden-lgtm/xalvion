from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger("xalvion.email")


def recipient_for_ticket_reply(ticket: Any) -> str:
    """Resolve outbound reply address from persisted ticket state (never ``username``)."""
    addr = str(getattr(ticket, "customer_email", None) or "").strip()
    if not addr or "@" not in addr:
        return ""
    return addr[:320]


def _smtp_settings() -> dict[str, str | int]:
    host = (os.getenv("XALVION_SMTP_HOST") or "").strip()
    port_raw = (os.getenv("XALVION_SMTP_PORT") or "587").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = (os.getenv("XALVION_SMTP_USER") or "").strip()
    password = (os.getenv("XALVION_SMTP_PASSWORD") or "").strip()
    mail_from = (os.getenv("XALVION_SMTP_FROM") or user or "").strip()
    return {"host": host, "port": port, "user": user, "password": password, "from": mail_from}


def smtp_ready() -> bool:
    s = _smtp_settings()
    return bool(s["host"] and s["from"])


def send_ticket_reply_email(
    *,
    ticket: Any,
    reply_body: str,
    subject: str | None = None,
) -> dict[str, Any]:
    """
    Send a customer-visible reply email.

    Returns a status dict. Missing ``customer_email`` yields ``pending_manual`` (callers
    should map to HTTP 400). Missing SMTP configuration yields ``transport_unavailable``.
    """
    to_addr = recipient_for_ticket_reply(ticket)
    if not to_addr:
        return {
            "status": "pending_manual",
            "code": "missing_customer_email",
            "message": "Ticket has no customer_email; reply cannot be delivered by email.",
        }

    body = (reply_body or "").strip()
    if not body:
        return {
            "status": "pending_manual",
            "code": "empty_reply_body",
            "message": "Reply body is empty; nothing to send.",
        }

    tid = getattr(ticket, "id", None)
    subj = (subject or "").strip() or f"Support update — ticket #{tid if tid is not None else '?'}"
    cfg = _smtp_settings()
    if not smtp_ready():
        return {
            "status": "transport_unavailable",
            "code": "smtp_not_configured",
            "message": "Outbound SMTP is not configured. Set XALVION_SMTP_HOST, XALVION_SMTP_FROM, "
            "and credentials (XALVION_SMTP_USER / XALVION_SMTP_PASSWORD) to send mail.",
            "to": to_addr,
        }

    msg = EmailMessage()
    msg["Subject"] = subj[:998]
    msg["From"] = str(cfg["from"])
    msg["To"] = to_addr
    msg.set_content(body)

    host = str(cfg["host"])
    port = int(cfg["port"])
    user = str(cfg["user"])
    password = str(cfg["password"])

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        logger.exception("ticket_reply_smtp_failed ticket_id=%s to=%s", tid, to_addr)
        return {
            "status": "error",
            "code": "smtp_send_failed",
            "message": str(exc)[:500],
            "to": to_addr,
        }

    logger.info("ticket_reply_sent ticket_id=%s to=%s", tid, to_addr)
    return {"status": "sent", "to": to_addr, "subject": subj}
