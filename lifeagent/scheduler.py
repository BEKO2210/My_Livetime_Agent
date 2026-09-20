"""Der Teil, der im Hintergrund mitläuft.

Einmal am Tag: Hinweise neu berechnen, Kurzmeldung verschicken, Sicherung anlegen.
Läuft im selben Prozess wie die Weboberfläche - kein zusätzlicher Dienst noetig.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .db import backup_database, session_scope
from .models import Alert
from .services import briefing as briefing_service
from .services import insights, notify, prefs

log = logging.getLogger("lifeagent.scheduler")
_scheduler: BackgroundScheduler | None = None


def run_daily_check(force_notify: bool = False) -> str:
    """Hinweise auffrischen und bei Bedarf benachrichtigen."""
    today = date.today()
    with session_scope() as session:
        insights.refresh_alerts(session, today)
        open_alerts = insights.open_alerts(session)

        # Nur über Dinge informieren, die noch nicht gemeldet wurden.
        fresh = [
            alert
            for alert in open_alerts
            if alert.severity in ("critical", "warn") and alert.notified_at is None
        ]
        if not fresh and not force_notify:
            return f"{len(open_alerts)} offene Hinweise, nichts Neues zu melden."

        text = briefing_service.build(session, today).as_text()
        title = f"{len(fresh)} neue Hinweise" if fresh else "Tagesübersicht"
        result = notify.send(session, title, text)
        if result.ok:
            stamp = datetime.now()
            for alert in fresh:
                session.get(Alert, alert.id).notified_at = stamp
        return f"{len(fresh)} neue Hinweise gemeldet ({result.detail})"


def start() -> BackgroundScheduler | None:
    """Startet den Hintergrundlauf. Mehrfachaufrufe sind unschaedlich."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    with session_scope() as session:
        hour = prefs.get_int(session, "briefing_hour", 8)
    hour = min(max(hour, 0), 23)

    scheduler = BackgroundScheduler(timezone="Europe/Berlin", daemon=True)
    scheduler.add_job(
        run_daily_check, "cron", hour=hour, minute=0, id="daily_check", replace_existing=True
    )
    scheduler.add_job(
        backup_database, "cron", hour=3, minute=30, id="backup", replace_existing=True
    )
    scheduler.start()
    _scheduler = scheduler
    log.info("Hintergrundlauf aktiv - tägliche Prüfung um %02d:00 Uhr", hour)
    return scheduler


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
