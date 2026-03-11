from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from .storage import Storage


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def smtp_configured() -> bool:
    return bool(_env("SMTP_HOST").strip())


def send_result_email(
    storage: Storage,
    *,
    to_email: str,
    subject: str,
    body_text: str,
    calc_id: str,
) -> str:
    """Returns a human-readable status string."""

    msg = EmailMessage()
    msg["To"] = to_email
    msg["From"] = _env("SMTP_FROM", "no-reply@example.com")
    msg["Subject"] = subject
    msg.set_content(body_text)

    host = _env("SMTP_HOST").strip()
    if not host:
        eml = msg.as_string()
        path = storage.write_outbox_eml(calc_id, subject, eml)
        return f"SMTP not configured; wrote email to {path}"

    port = int(_env("SMTP_PORT", "587") or "587")
    user = _env("SMTP_USER").strip()
    password = _env("SMTP_PASS").strip()

    # Use STARTTLS by default for 587.
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.ehlo()
        try:
            s.starttls()
            s.ehlo()
        except smtplib.SMTPException:
            # allow non-TLS
            pass
        if user and password:
            s.login(user, password)
        s.send_message(msg)

    return "sent via SMTP"
