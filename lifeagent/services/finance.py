"""Auswertungen: Was kostet mich mein Leben, was kommt rein, was bleibt?"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..dates import add_months
from ..models import Contract, Transaction


def month_bounds(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    return first, add_months(first, 1)


@dataclass
class MonthSummary:
    month: date
    income_cents: int = 0
    expense_cents: int = 0

    @property
    def balance_cents(self) -> int:
        return self.income_cents - self.expense_cents

    @property
    def label(self) -> str:
        names = [
            "Jan",
            "Feb",
            "Mrz",
            "Apr",
            "Mai",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Okt",
            "Nov",
            "Dez",
        ]
        return f"{names[self.month.month - 1]} {self.month.year}"


@dataclass
class FixedCosts:
    monthly_cents: int = 0
    yearly_cents: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    active_count: int = 0

    @property
    def top_categories(self) -> list[tuple[str, int]]:
        return sorted(self.by_category.items(), key=lambda kv: kv[1], reverse=True)


def fixed_costs(session: Session) -> FixedCosts:
    """Summe aller laufenden Vertragskosten, normiert auf einen Monat."""
    result = FixedCosts()
    contracts = session.query(Contract).filter(Contract.status == "active").all()
    for contract in contracts:
        result.active_count += 1
        monthly = contract.monthly_cents
        if monthly <= 0:
            continue
        result.monthly_cents += monthly
        result.yearly_cents += contract.yearly_cents
        key = contract.category or "Sonstiges"
        result.by_category[key] = result.by_category.get(key, 0) + monthly
    return result


def month_summary(session: Session, day: date) -> MonthSummary:
    start, end = month_bounds(day)
    rows = (
        session.query(Transaction)
        .filter(Transaction.booking_date >= start, Transaction.booking_date < end)
        .all()
    )
    summary = MonthSummary(month=start)
    for row in rows:
        if row.amount_cents >= 0:
            summary.income_cents += row.amount_cents
        else:
            summary.expense_cents += -row.amount_cents
    return summary


def month_series(session: Session, today: date, months: int = 6) -> list[MonthSummary]:
    """Die letzten N Monate als Zeitreihe (ältester zuerst)."""
    start = add_months(today.replace(day=1), -(months - 1))
    rows = (
        session.query(Transaction)
        .filter(Transaction.booking_date >= start)
        .order_by(Transaction.booking_date)
        .all()
    )
    buckets: dict[date, MonthSummary] = {}
    for offset in range(months):
        key = add_months(start, offset)
        buckets[key] = MonthSummary(month=key)
    for row in rows:
        key = row.booking_date.replace(day=1)
        bucket = buckets.get(key)
        if bucket is None:
            continue
        if row.amount_cents >= 0:
            bucket.income_cents += row.amount_cents
        else:
            bucket.expense_cents += -row.amount_cents
    return [buckets[key] for key in sorted(buckets)]


def average_monthly_income(session: Session, today: date, months: int = 3) -> int:
    """Durchschnittliche Einnahmen der letzten abgeschlossenen Monate."""
    series = month_series(session, today, months + 1)[:-1]  # laufenden Monat auslassen
    series = [m for m in series if m.income_cents > 0]
    if not series:
        return 0
    return sum(m.income_cents for m in series) // len(series)


def spending_by_category(session: Session, today: date, months: int = 1) -> list[tuple[str, int]]:
    start = add_months(today.replace(day=1), -(months - 1))
    rows = (
        session.query(Transaction.category, func.sum(Transaction.amount_cents))
        .filter(Transaction.booking_date >= start, Transaction.amount_cents < 0)
        .group_by(Transaction.category)
        .all()
    )
    totals: dict[str, int] = defaultdict(int)
    for category, total in rows:
        totals[category or "Nicht zugeordnet"] += -int(total or 0)
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def upcoming_payments(session: Session, today: date, days: int = 30) -> list[dict]:
    """Welche Abbuchungen stehen in den nächsten Tagen an?"""
    horizon = date.fromordinal(today.toordinal() + days)
    items = []
    for contract in session.query(Contract).filter(Contract.status == "active").all():
        due = contract.timing(today).next_payment
        if due and today <= due <= horizon and contract.amount_cents > 0:
            items.append(
                {
                    "contract": contract,
                    "due": due,
                    "days": (due - today).days,
                    "amount_cents": contract.amount_cents,
                }
            )
    return sorted(items, key=lambda item: item["due"])


def upcoming_deadlines(session: Session, today: date, days: int = 90) -> list[dict]:
    """Kündigungsfristen, die bald ablaufen."""
    items = []
    for contract in session.query(Contract).filter(Contract.status == "active").all():
        timing = contract.timing(today)
        if timing.cancel_by is None:
            continue
        days_left = (timing.cancel_by - today).days
        if days_left < 0 or days_left > days:
            continue
        items.append(
            {
                "contract": contract,
                "cancel_by": timing.cancel_by,
                "period_end": timing.period_end,
                "days": days_left,
                "urgency": timing.urgency,
            }
        )
    return sorted(items, key=lambda item: item["cancel_by"])
