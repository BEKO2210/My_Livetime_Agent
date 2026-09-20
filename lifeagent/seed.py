"""Beispieldaten zum Ausprobieren.

Bewusst so gebaut, dass alle Fähigkeiten des Buddys sichtbar werden:
eine Frist, die bald abläuft; zwei Streaming-Abos; eine Preiserhöhung;
ein Abo im Kontoauszug, zu dem kein Vertrag hinterlegt ist.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from .dates import add_months
from .models import Contract, Transaction
from .services.ledger import add_transaction


def create_demo_data(session: Session, today: date | None = None) -> str:
    today = today or date.today()

    def buchen(tage: int, betrag: int, wer: str, zweck: str, kategorie: str = "") -> None:
        """Legt eine Buchung an, solange sie nicht in der Zukunft liegt."""
        tag = month_start + timedelta(days=tage)
        if tag > today:
            return
        add_transaction(
            session,
            booking_date=tag,
            amount_cents=betrag,
            counterparty=wer,
            purpose=zweck,
            category=kategorie,
            source="beispiel",
        )

    if session.query(Contract).count() or session.query(Transaction).count():
        return "Es sind bereits Daten vorhanden - Beispieldaten wurden nicht angelegt."

    contracts = [
        Contract(
            name="Mobilfunk Vertrag",
            provider="Telekom",
            kind="vertrag",
            category="Mobilfunk & Internet",
            amount_cents=3999,
            interval="monthly",
            # Frist läuft in gut vier Wochen ab -> erzeugt eine Warnung
            start_date=add_months(today, -23) + timedelta(days=5),
            minimum_term_months=24,
            renewal_months=12,
            notice_months=0,
            notice_days=30,
            customer_number="MB-4711",
        ),
        Contract(
            name="Netflix Standard",
            provider="Netflix",
            kind="abo",
            category="Streaming & Medien",
            amount_cents=1399,
            interval="monthly",
            start_date=add_months(today, -14),
            notice_months=1,
        ),
        Contract(
            name="Disney+",
            provider="Disney",
            kind="abo",
            category="Streaming & Medien",
            amount_cents=899,
            interval="monthly",
            start_date=add_months(today, -8),
            notice_months=1,
        ),
        Contract(
            name="Hausratversicherung",
            provider="HUK-COBURG",
            kind="versicherung",
            category="Versicherung",
            amount_cents=13200,
            interval="yearly",
            start_date=add_months(today, -20),
            minimum_term_months=12,
            renewal_months=12,
            notice_months=3,
            customer_number="HR-998123",
        ),
        Contract(
            name="Fitnessstudio",
            provider="FitX",
            kind="mitgliedschaft",
            category="Sport & Fitness",
            amount_cents=2999,
            interval="monthly",
            start_date=add_months(today, -30),
            minimum_term_months=12,
            renewal_months=12,
            notice_months=3,
        ),
        Contract(
            name="Miete Wohnung",
            provider="Hausverwaltung Müller",
            kind="miete",
            category="Wohnen",
            amount_cents=98000,
            interval="monthly",
            start_date=add_months(today, -40),
            notice_months=3,
        ),
    ]
    session.add_all(contracts)
    session.flush()

    # Kontoumsätze der letzten zwoelf Monate inklusive des laufenden
    for offset in range(12, -1, -1):
        month_start = add_months(today.replace(day=1), -offset)

        if month_start > today:
            continue

        buchen(0, 285000, "ARBEITGEBER GMBH", f"Gehalt {month_start:%m/%Y}", "Gehalt")
        buchen(2, -98000, "Hausverwaltung Müller", "Miete inkl. Nebenkosten")
        buchen(3, -3999, "TELEKOM DEUTSCHLAND GMBH", "Mobilfunk Rechnung")
        # Netflix ist seit drei Monaten teurer -> die Preiserhöhung wird erkannt
        buchen(5, -1399 if offset > 3 else -1799, "NETFLIX INTERNATIONAL B.V.", "Abo")
        buchen(6, -899, "DISNEY PLUS", "Monatsabo")
        buchen(7, -2999, "FITX GMBH", "Mitgliedsbeitrag")
        # Zu Spotify ist bewusst kein Vertrag hinterlegt -> der Buddy schlaegt einen vor
        buchen(9, -1099, "SPOTIFY AB", "Premium Family")
        buchen(11, -8500, "STADTWERKE", "Abschlag Strom")
        # Einkäufe schwanken - so wie im echten Leben
        schwankung = (offset * 1379) % 2600
        buchen(12, -(5200 + schwankung), "REWE MARKT", "Einkauf", "Lebensmittel")
        buchen(18, -(3400 + schwankung // 2), "EDEKA", "Einkauf", "Lebensmittel")
        buchen(24, -(6100 + schwankung), "KAUFLAND", "Einkauf", "Lebensmittel")

    session.flush()
    return (
        f"Beispieldaten angelegt: {session.query(Contract).count()} Verträge, "
        f"{session.query(Transaction).count()} Buchungen. "
        "Zum Löschen einfach data/lifeagent.db entfernen."
    )
