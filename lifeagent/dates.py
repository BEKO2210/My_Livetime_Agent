"""Termin- und Fristenrechnung für Verträge und Abos.

Kernfragen, die dieses Modul beantwortet:
  * Wann läuft der Vertrag aktuell aus?          -> term_end()
  * Bis wann muss ich spätestens kündigen?      -> cancel_deadline()
  * Wann wird das nächste Mal abgebucht?         -> next_due()
  * Was kostet das Ganze pro Monat / pro Jahr?    -> monthly_cents()
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

ONE_DAY = timedelta(days=1)

# Zahlungsintervall -> Anzahl Monate (None = kein wiederkehrender Rhythmus)
INTERVAL_MONTHS: dict[str, int | None] = {
    "weekly": None,  # Sonderfall, wird über Tage gerechnet
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "yearly": 12,
    "once": None,
    "none": None,
}

INTERVAL_LABELS: dict[str, str] = {
    "weekly": "wöchentlich",
    "monthly": "monatlich",
    "quarterly": "vierteljährlich",
    "semiannual": "halbjährlich",
    "yearly": "jährlich",
    "once": "einmalig",
    "none": "keine Zahlung",
}

# Wie oft pro Jahr wird gezahlt
INTERVAL_PER_YEAR: dict[str, Decimal] = {
    "weekly": Decimal("52"),
    "monthly": Decimal("12"),
    "quarterly": Decimal("4"),
    "semiannual": Decimal("2"),
    "yearly": Decimal("1"),
    "once": Decimal("0"),
    "none": Decimal("0"),
}


def add_months(d: date, months: int) -> date:
    """Addiert Monate und behält den Monatsletzten korrekt (31.01 + 1M = 28./29.02)."""
    if months == 0:
        return d
    total = d.year * 12 + (d.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_date(value) -> date | None:
    """Liest Datumsangaben aus Formularen und Bank-CSVs (TT.MM.JJJJ, JJJJ-MM-TT, ...)."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime

            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if fmt.endswith("%y") and parsed.year < 1970:
            parsed = parsed.replace(year=parsed.year + 100)
        return parsed
    return None


def term_end(
    start: date | None,
    minimum_term_months: int,
    renewal_months: int,
    today: date | None = None,
) -> date | None:
    """Ende der aktuellen Vertragsperiode.

    None bedeutet: unbefristet / läuft ohne feste Periode weiter
    (z.B. monatlich kündbar, wie es für Verträge ab 01.03.2022 üblich ist).
    """
    if start is None:
        return None
    today = today or date.today()
    minimum_term_months = max(0, int(minimum_term_months or 0))
    renewal_months = max(0, int(renewal_months or 0))

    if minimum_term_months == 0 and renewal_months == 0:
        return None

    if minimum_term_months > 0:
        end = add_months(start, minimum_term_months) - ONE_DAY
    else:
        end = add_months(start, renewal_months) - ONE_DAY

    if renewal_months == 0:
        # Nach der Mindestlaufzeit geht es unbefristet weiter.
        return end if end >= today else None

    guard = 0
    while end < today and guard < 400:
        end = add_months(end + ONE_DAY, renewal_months) - ONE_DAY
        guard += 1
    return end


def cancel_deadline(
    period_end: date | None,
    notice_months: int = 0,
    notice_days: int = 0,
) -> date | None:
    """Letzter Tag, an dem die Kündigung beim Anbieter sein muss."""
    if period_end is None:
        return None
    deadline = period_end
    if notice_months:
        deadline = add_months(deadline, -int(notice_months))
    if notice_days:
        deadline = deadline - timedelta(days=int(notice_days))
    return deadline


def earliest_exit(
    today: date,
    notice_months: int = 0,
    notice_days: int = 0,
) -> date:
    """Früheste Beendigung bei unbefristeten Verträgen (ab heute gekündigt)."""
    end = today
    if notice_months:
        end = add_months(end, int(notice_months))
    if notice_days:
        end = end + timedelta(days=int(notice_days))
    return end


def next_due(
    start: date | None,
    interval: str,
    today: date | None = None,
    until: date | None = None,
) -> date | None:
    """Nächster Zahlungstermin ab heute."""
    if start is None:
        return None
    today = today or date.today()
    interval = (interval or "none").lower()

    if interval in ("once", "none"):
        return start if start >= today else None

    if until and until < today:
        return None

    if interval == "weekly":
        if start >= today:
            candidate = start
        else:
            weeks = ((today - start).days + 6) // 7
            candidate = start + timedelta(weeks=weeks)
        return candidate if not until or candidate <= until else None

    step = INTERVAL_MONTHS.get(interval)
    if not step:
        return None

    if start >= today:
        candidate = start
    else:
        months_apart = (today.year - start.year) * 12 + (today.month - start.month)
        periods = months_apart // step
        candidate = add_months(start, periods * step)
        guard = 0
        while candidate < today and guard < 400:
            candidate = add_months(candidate, step)
            guard += 1
    return candidate if not until or candidate <= until else None


def monthly_cents(amount_cents: int, interval: str) -> int:
    """Rechnet einen Betrag auf Monatskosten um (einmalige Zahlungen zählen nicht)."""
    per_year = INTERVAL_PER_YEAR.get((interval or "none").lower(), Decimal("0"))
    if per_year == 0 or not amount_cents:
        return 0
    value = (Decimal(int(amount_cents)) * per_year) / Decimal("12")
    return int(value.quantize(Decimal("1"), ROUND_HALF_UP))


def yearly_cents(amount_cents: int, interval: str) -> int:
    per_year = INTERVAL_PER_YEAR.get((interval or "none").lower(), Decimal("0"))
    if per_year == 0 or not amount_cents:
        return 0
    return int((Decimal(int(amount_cents)) * per_year).quantize(Decimal("1"), ROUND_HALF_UP))


@dataclass(frozen=True)
class Timing:
    """Alle Termin-Infos zu einem Vertrag auf einen Blick."""

    period_end: date | None
    cancel_by: date | None
    days_until_cancel: int | None
    open_ended: bool
    next_payment: date | None

    @property
    def urgency(self) -> str:
        """critical (<= 14 Tage), warning (<= 45), ok, oder none."""
        if self.days_until_cancel is None:
            return "none"
        if self.days_until_cancel < 0:
            return "expired"
        if self.days_until_cancel <= 14:
            return "critical"
        if self.days_until_cancel <= 45:
            return "warning"
        return "ok"


def timing_for(
    start: date | None,
    interval: str,
    minimum_term_months: int = 0,
    renewal_months: int = 0,
    notice_months: int = 0,
    notice_days: int = 0,
    end_date: date | None = None,
    today: date | None = None,
) -> Timing:
    """Bequemer Sammelaufruf für die Vertragsansicht."""
    today = today or date.today()
    period = term_end(start, minimum_term_months, renewal_months, today)
    open_ended = period is None

    if open_ended:
        deadline = None
        days = None
    else:
        deadline = cancel_deadline(period, notice_months, notice_days)
        days = (deadline - today).days if deadline else None

    return Timing(
        period_end=period,
        cancel_by=deadline,
        days_until_cancel=days,
        open_ended=open_ended,
        next_payment=next_due(start, interval, today, until=end_date),
    )
