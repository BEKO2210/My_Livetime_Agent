"""Startpunkt: python -m lifeagent

Optionen:
  python -m lifeagent              Weboberfläche starten
  python -m lifeagent --pruefen    einmalig Hinweise berechnen und melden
  python -m lifeagent --beispiel   Beispieldaten anlegen (zum Ausprobieren)
  python -m lifeagent --briefing   Tagesübersicht im Terminal ausgeben
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from datetime import date

from .config import settings
from .db import init_db, session_scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lifeagent", description="Dein persoenlicher Alltags-Agent"
    )
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    # Beide Schreibweisen, damit niemand ein Sonderzeichen tippen muss.
    parser.add_argument(
        "--pruefen",
        "--prüfen",
        dest="pruefen",
        action="store_true",
        help="einmalig prüfen und benachrichtigen",
    )
    parser.add_argument("--briefing", action="store_true", help="Tagesübersicht ausgeben")
    parser.add_argument("--beispiel", action="store_true", help="Beispieldaten anlegen")
    parser.add_argument("--kein-browser", action="store_true", help="Browser nicht öffnen")
    args = parser.parse_args(argv)

    init_db()

    if args.beispiel:
        from .seed import create_demo_data

        with session_scope() as session:
            summary = create_demo_data(session)
        print(summary)
        return 0

    if args.briefing:
        from .services import briefing as briefing_service
        from .services import insights

        with session_scope() as session:
            insights.refresh_alerts(session, date.today())
            print(briefing_service.build(session, date.today()).as_text())
        return 0

    if args.pruefen:
        from .scheduler import run_daily_check

        print(run_daily_check(force_notify=True))
        return 0

    import uvicorn

    from .web.app import app

    if settings.enable_scheduler:
        from . import scheduler

        scheduler.start()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  Life Agent läuft:  {url}")
    print(f"  Daten:              {settings.db_path}")
    print("  Beenden mit Strg+C\n")

    if not args.kein_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
