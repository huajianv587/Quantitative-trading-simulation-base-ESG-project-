from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from gateway.auth.repository import get_auth_repository
from gateway.config import settings


def smtp_ready() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD)


def smtp_config_snapshot() -> dict[str, Any]:
    return {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user_set": bool(settings.SMTP_USER),
        "password_set": bool(settings.SMTP_PASSWORD),
        "sender": settings.EMAIL_FROM or settings.SMTP_USER,
        "ready": smtp_ready(),
    }


def send_email_message(
    *,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    sender: str | None = None,
    reply_to: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    repo = get_auth_repository()
    if not smtp_ready():
        payload = {"ok": False, "detail": "smtp_not_configured", "config": smtp_config_snapshot()}
        repo.record_mailbox_delivery(
            recipient=recipient,
            subject=subject,
            status="failed",
            detail="smtp_not_configured",
            metadata=payload["config"],
        )
        return payload

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender or settings.EMAIL_FROM or settings.SMTP_USER
    message["To"] = recipient
    if reply_to:
        message["Reply-To"] = reply_to

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        message.attach(MIMEText(html_body, "html", "utf-8"))

    host = settings.SMTP_HOST
    port = int(settings.SMTP_PORT or 587)
    username = settings.SMTP_USER
    password = settings.SMTP_PASSWORD

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)

        with server:
            server.ehlo()
            if port != 465:
                server.starttls()
                server.ehlo()
            server.login(username, password)
            server.send_message(message)

        payload = {
            "ok": True,
            "detail": "sent",
            "recipient": recipient,
            "subject": subject,
            "config": smtp_config_snapshot(),
        }
        repo.record_mailbox_delivery(
            recipient=recipient,
            subject=subject,
            status="sent",
            detail="smtp_accepted",
            metadata=payload["config"],
        )
        return payload
    except Exception as exc:  # pragma: no cover - runtime path
        payload = {
            "ok": False,
            "detail": str(exc),
            "recipient": recipient,
            "subject": subject,
            "config": smtp_config_snapshot(),
        }
        repo.record_mailbox_delivery(
            recipient=recipient,
            subject=subject,
            status="failed",
            detail=str(exc),
            metadata=payload["config"],
        )
        return payload
