from __future__ import annotations

import datetime as dt
import smtplib
from email.message import EmailMessage
from typing import List

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Alert


def _record(
    db: Session,
    trade_date: dt.date,
    channel: str,
    subject: str,
    body: str,
    status: str,
    error: str = "",
) -> Alert:
    alert = Alert(
        trade_date=trade_date,
        channel=channel,
        subject=subject,
        body=body,
        status=status,
        error=error,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def send_telegram(settings: Settings, subject: str, body: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured")
    text = f"{subject}\n\n{body}"
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    with httpx.Client(timeout=30) as client:
        response = client.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": text[:4000]},
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")


def send_slack(settings: Settings, subject: str, body: str) -> None:
    if not settings.slack_webhook_url:
        raise RuntimeError("Slack webhook is not configured")
    with httpx.Client(timeout=30) as client:
        response = client.post(
            settings.slack_webhook_url,
            json={"text": f"*{subject}*\n```{body[:3500]}```"},
        )
        response.raise_for_status()


def send_email(settings: Settings, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_to or not settings.smtp_from:
        raise RuntimeError("Email/SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_to
    message.set_content(body)

    if settings.smtp_use_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(message)


def send_digest(
    db: Session,
    trade_date: dt.date,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> List[Alert]:
    settings = settings or get_settings()
    results: List[Alert] = []

    channels = [
        ("telegram", send_telegram, bool(settings.telegram_bot_token and settings.telegram_chat_id)),
        ("email", send_email, bool(settings.smtp_host and settings.smtp_to and settings.smtp_from)),
        ("slack", send_slack, bool(settings.slack_webhook_url)),
    ]

    configured = [(name, fn) for name, fn, enabled in channels if enabled]
    if not configured:
        results.append(
            _record(
                db,
                trade_date,
                "none",
                subject,
                body,
                "skipped",
                "No notification channels configured",
            )
        )
        return results

    for name, fn in configured:
        try:
            fn(settings, subject, body)
            results.append(_record(db, trade_date, name, subject, body, "sent"))
        except Exception as exc:  # noqa: BLE001
            results.append(_record(db, trade_date, name, subject, body, "failed", str(exc)))
    return results
