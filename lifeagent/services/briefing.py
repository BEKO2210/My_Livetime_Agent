"""Die tägliche Kurzmeldung des Buddys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from ..money import format_cents
from . import finance, insights, prefs

WEEKDAYS = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]


@dataclass
class Briefing:
    day: date
    greeting: str
    headline: str
    lines: list[str] = field(default_factory=list)
    alerts: list = field(default_factory=list)
    payments: list = field(default_factory=list)

    @property
    def has_news(self) -> bool:
        return bool(self.alerts or self.payments)

    def as_text(self) -> str:
        parts = [self.greeting, "", self.headline, ""]
        parts += [f"- {line}" for line in self.lines]
        return "\n".join(parts).strip()


def _greeting(owner: str, day: date) -> str:
    name = f" {owner}" if owner else ""
    return f"Guten Morgen{name} - {WEEKDAYS[day.weekday()]}, {day:%d.%m.%Y}"


def build(session: Session, today: date | None = None) -> Briefing:
    today = today or date.today()
    owner = prefs.get(session, "owner_name", "")
    currency = prefs.get(session, "currency", "EUR")

    alerts = insights.open_alerts(session)
    urgent = [a for a in alerts if a.severity in ("critical", "warn")]
    payments = finance.upcoming_payments(session, today, days=7)
    costs = finance.fixed_costs(session)
    month = finance.month_summary(session, today)

    if not urgent:
        headline = "Alles im Griff - keine dringenden Fristen."
    elif len(urgent) == 1:
        headline = f"Eine Sache braucht dich heute: {urgent[0].title}"
    else:
        headline = f"{len(urgent)} Dinge brauchen dich heute."

    lines: list[str] = []
    for alert in urgent[:5]:
        suffix = f" (bis {alert.due_date:%d.%m.})" if alert.due_date else ""
        lines.append(f"{alert.severity_label}: {alert.title}{suffix}")

    if payments:
        total = sum(p["amount_cents"] for p in payments)
        lines.append(
            f"In den nächsten 7 Tagen werden {format_cents(total, currency)} abgebucht "
            f"({len(payments)} Zahlungen)."
        )

    lines.append(
        f"Feste Kosten: {format_cents(costs.monthly_cents, currency)} im Monat "
        f"aus {costs.active_count} laufenden Verträgen."
    )
    lines.append(
        f"Dieser Monat: {format_cents(month.income_cents, currency)} rein, "
        f"{format_cents(month.expense_cents, currency)} raus, "
        f"Saldo {format_cents(month.balance_cents, currency, signed=True)}."
    )

    return Briefing(
        day=today,
        greeting=_greeting(owner, today),
        headline=headline,
        lines=lines,
        alerts=alerts,
        payments=payments,
    )
