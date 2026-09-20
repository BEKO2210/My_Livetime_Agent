"""Benachrichtigungen nach draußen.

Standard ist "app": es wird nichts verschickt, die Hinweise stehen in der
Oberfläche. Wer eine Push-Nachricht aufs Handy will, traegt ein ntfy-Topic
ein (kostenlos, keine Anmeldung). E-Mail über den eigenen SMTP-Server geht auch.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy.orm import Session

from . import prefs


@dataclass
class NotifyResult:
    ok: bool
    channel: str
    detail: str = ""


def send(session: Session, title: str, body: str) -> NotifyResult:
    channel = prefs.get(session, "notify_channel", "app")
    if channel == "ntfy":
        return _send_ntfy(session, title, body)
    if channel == "email":
        return _send_email(session, title, body)
    return NotifyResult(ok=True, channel="app", detail="Hinweis nur in der App hinterlegt.")


def _send_ntfy(session: Session, title: str, body: str) -> NotifyResult:
    topic = prefs.get(session, "ntfy_topic", "").strip()
    server = prefs.get(session, "ntfy_server", "https://ntfy.sh").rstrip("/")
    if not topic:
        return NotifyResult(False, "ntfy", "Es ist kein ntfy-Topic eingetragen.")
    try:
        import httpx

        response = httpx.post(
            f"{server}/{topic}",
            content=body.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8").decode("latin-1", "ignore"),
                "Priority": "default",
                "Tags": "bell",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return NotifyResult(True, "ntfy", f"An {server}/{topic} gesendet.")
    except Exception as error:  # pragma: no cover - Netzwerk
        return NotifyResult(False, "ntfy", f"Senden fehlgeschlagen: {error}")


def _send_email(session: Session, title: str, body: str) -> NotifyResult:
    host = prefs.get(session, "smtp_host", "").strip()
    port = prefs.get_int(session, "smtp_port", 587)
    user = prefs.get(session, "smtp_user", "").strip()
    password = prefs.get(session, "smtp_password", "")
    sender = prefs.get(session, "smtp_from", "").strip() or user
    recipient = prefs.get(session, "smtp_to", "").strip() or sender

    if not host or not recipient:
        return NotifyResult(False, "email", "SMTP-Server oder Empfänger fehlt.")

    message = EmailMessage()
    message["Subject"] = title
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    try:  # pragma: no cover - Netzwerk
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                if user:
                    server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=context)
                if user:
                    server.login(user, password)
                server.send_message(message)
        return NotifyResult(True, "email", f"E-Mail an {recipient} gesendet.")
    except Exception as error:  # pragma: no cover - Netzwerk
        return NotifyResult(False, "email", f"Senden fehlgeschlagen: {error}")
