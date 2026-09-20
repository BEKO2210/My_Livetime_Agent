"""Der wachsame Teil des Buddys.

Hier steckt die eigentliche Arbeit: aus Verträgen und Kontobuchungen werden
konkrete Hinweise ("du zahlst zweimal für Streaming", "Frist läuft in 9 Tagen",
"hier ist der Preis gestiegen"). Alles rein rechnerisch und lokal.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from ..dates import add_months
from ..models import Alert, Contract, Transaction
from ..money import format_cents
from . import finance, prefs
from .matching import signature

SEVERITY_ORDER = {"critical": 0, "warn": 1, "info": 2}

# Händler, bei denen regelmäßige Buchungen normal sind - das sind keine Abos.
NON_SUBSCRIPTION_CATEGORIES = {"Lebensmittel", "Einkauf", "Mobilität"}


@dataclass
class Finding:
    key: str
    kind: str
    severity: str
    title: str
    message: str
    action_url: str = ""
    contract_id: int | None = None
    due_date: date | None = None


@dataclass
class RecurringGroup:
    signature: str
    label: str
    amounts: list[int] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)
    contract_ids: set[int] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)
    transaction_ids: list[int] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.dates)

    @property
    def last_date(self) -> date:
        return max(self.dates)

    @property
    def typical_amount(self) -> int:
        return int(statistics.median(self.amounts))

    @property
    def average_gap_days(self) -> float:
        if len(self.dates) < 2:
            return 0.0
        ordered = sorted(self.dates)
        gaps = [(b - a).days for a, b in zip(ordered, ordered[1:])]
        return sum(gaps) / len(gaps)

    @property
    def latest_amount(self) -> int:
        """Der zuletzt gebuchte Betrag - wichtig nach einer Preiserhöhung."""
        return max(zip(self.dates, self.amounts))[1]

    @property
    def is_subscription_candidate(self) -> bool:
        """Supermarkt und Tankstelle sind keine Abos, auch wenn sie regelmäßig kommen."""
        return not (self.categories & NON_SUBSCRIPTION_CATEGORIES)

    @property
    def rhythm(self) -> str | None:
        gap = self.average_gap_days
        if 25 <= gap <= 35:
            return "monatlich"
        if 6 <= gap <= 8:
            return "wöchentlich"
        if 85 <= gap <= 95:
            return "vierteljährlich"
        if 175 <= gap <= 190:
            return "halbjährlich"
        if 355 <= gap <= 375:
            return "jährlich"
        return None


def recurring_groups(
    session: Session,
    today: date,
    months_back: int = 12,
    min_occurrences: int = 3,
) -> list[RecurringGroup]:
    """Findet wiederkehrende Abbuchungen im Kontoverlauf."""
    since = add_months(today, -months_back)
    rows = (
        session.query(Transaction)
        .filter(Transaction.booking_date >= since, Transaction.amount_cents < 0)
        .all()
    )
    buckets: dict[str, RecurringGroup] = {}
    for row in rows:
        key = signature(row.counterparty, row.purpose)
        if len(key) < 3:
            continue
        group = buckets.setdefault(
            key, RecurringGroup(signature=key, label=row.counterparty or row.purpose[:40])
        )
        group.amounts.append(-row.amount_cents)
        group.dates.append(row.booking_date)
        group.transaction_ids.append(row.id)
        if row.category:
            group.categories.add(row.category)
        if row.contract_id:
            group.contract_ids.add(row.contract_id)

    result = []
    for group in buckets.values():
        if group.count < min_occurrences:
            continue
        if group.rhythm is None:
            continue
        typical = group.typical_amount
        if typical <= 0:
            continue
            # Beträge müssen halbwegs stabil sein, sonst ist es Einkaufen, kein Abo.
        spread = max(group.amounts) - min(group.amounts)
        if typical and spread > max(300, typical * 0.35):
            continue
        result.append(group)
    return sorted(result, key=lambda g: g.typical_amount, reverse=True)

    # --------------------------------------------------------------------------- #
    # Einzelne Prüfungen
    # --------------------------------------------------------------------------- #


def check_deadlines(session: Session, today: date, default_lead: int) -> list[Finding]:
    findings: list[Finding] = []
    for contract in session.query(Contract).filter(Contract.status == "active").all():
        timing = contract.timing(today)
        if timing.cancel_by is None:
            continue
        lead = contract.lead_days(default_lead)
        days = (timing.cancel_by - today).days

        if 0 <= days <= lead:
            severity = "critical" if days <= 14 else "warn"
            findings.append(
                Finding(
                    key=f"deadline:{contract.id}:{timing.cancel_by.isoformat()}",
                    kind="deadline",
                    severity=severity,
                    title=f"Kündigungsfrist: {contract.name}",
                    message=(
                        f"Wenn du {contract.name} nicht weiterführen willst, muss die "
                        f"Kündigung bis zum {timing.cancel_by:%d.%m.%Y} raus "
                        f"(noch {days} Tage). Sonst läuft der Vertrag bis "
                        f"{timing.period_end:%d.%m.%Y} weiter und verlängert sich."
                    ),
                    action_url=f"/vertraege/{contract.id}",
                    contract_id=contract.id,
                    due_date=timing.cancel_by,
                )
            )
        elif -7 <= days < 0 and timing.period_end:
            findings.append(
                Finding(
                    key=f"renewed:{contract.id}:{timing.period_end.isoformat()}",
                    kind="renewed",
                    severity="info",
                    title=f"Verlängert sich: {contract.name}",
                    message=(
                        f"Die Kündigungsfrist für {contract.name} ist seit "
                        f"{abs(days)} Tagen abgelaufen. Der Vertrag läuft bis "
                        f"{timing.period_end:%d.%m.%Y} weiter. Nächste Chance rechtzeitig vormerken."
                    ),
                    action_url=f"/vertraege/{contract.id}",
                    contract_id=contract.id,
                    due_date=timing.period_end,
                )
            )
    return findings


def check_incomplete_contracts(session: Session, today: date) -> list[Finding]:
    findings = []
    for contract in session.query(Contract).filter(Contract.status == "active").all():
        if contract.start_date is None:
            findings.append(
                Finding(
                    key=f"incomplete:{contract.id}",
                    kind="incomplete",
                    severity="info",
                    title=f"Angaben fehlen: {contract.name}",
                    message=(
                        "Ohne Vertragsbeginn kann ich keine Kündigungsfrist berechnen. "
                        "Trag das Startdatum nach, dann passe ich auf."
                    ),
                    action_url=f"/vertraege/{contract.id}",
                    contract_id=contract.id,
                )
            )
    return findings


def check_untracked_subscriptions(session: Session, today: date) -> list[Finding]:
    """Regelmäßige Abbuchungen, zu denen kein Vertrag hinterlegt ist."""
    findings = []
    for group in recurring_groups(session, today):
        if group.contract_ids:
            continue
        if not group.is_subscription_candidate:
            continue
        if (today - group.last_date).days > 70:
            continue
        monthly_hint = {
            "wöchentlich": group.typical_amount * 52 // 12,
            "monatlich": group.typical_amount,
            "vierteljährlich": group.typical_amount // 3,
            "halbjährlich": group.typical_amount // 6,
            "jährlich": group.typical_amount // 12,
        }.get(group.rhythm or "", group.typical_amount)
        findings.append(
            Finding(
                key=f"untracked:{group.signature}",
                kind="untracked",
                severity="warn",
                title=f"Unbekanntes Abo: {group.label}",
                message=(
                    f"Seit {group.count} Buchungen gehen {format_cents(group.typical_amount)} "
                    f"{group.rhythm} an {group.label} raus "
                    f"(rund {format_cents(monthly_hint)} im Monat), "
                    "aber dazu ist kein Vertrag hinterlegt. Soll ich den anlegen?"
                ),
                action_url=f"/vertraege/neu?aus_buchung={group.transaction_ids[-1]}",
            )
        )
    return findings


def check_price_increases(session: Session, today: date) -> list[Finding]:
    """Preiserhöhungen bei wiederkehrenden Zahlungen."""
    findings = []
    for group in recurring_groups(session, today, min_occurrences=3):
        if not group.is_subscription_candidate:
            continue  # schwankende Einkaufsbeträge sind keine Preiserhöhung
        ordered = [a for _, a in sorted(zip(group.dates, group.amounts))]
        latest = ordered[-1]
        history = ordered[:-1]
        if not history:
            continue
        baseline = int(statistics.median(history))
        if baseline <= 0:
            continue
        delta = latest - baseline
        if delta < 100 or delta / baseline < 0.05:
            continue
        percent = delta / baseline * 100
        findings.append(
            Finding(
                key=f"price:{group.signature}:{latest}",
                kind="price",
                severity="warn",
                title=f"Preis gestiegen: {group.label}",
                message=(
                    f"{group.label} kostet jetzt {format_cents(latest)} statt "
                    f"{format_cents(baseline)} - das sind {percent:.0f} % mehr "
                    f"bzw. {format_cents(delta * 12)} im Jahr. "
                    "Bei Preiserhöhungen hast du oft ein Sonderkündigungsrecht."
                ),
                action_url="/finanzen",
                contract_id=next(iter(group.contract_ids), None),
            )
        )
    return findings


def check_missing_payments(session: Session, today: date) -> list[Finding]:
    """Erwartete Abbuchung ist ausgeblieben - Rücklastschrift oder Kontowechsel?"""
    findings = []
    contracts = (
        session.query(Contract)
        .filter(Contract.status == "active", Contract.interval == "monthly")
        .all()
    )
    for contract in contracts:
        rows = (
            session.query(Transaction)
            .filter(Transaction.contract_id == contract.id, Transaction.amount_cents < 0)
            .order_by(Transaction.booking_date.desc())
            .limit(6)
            .all()
        )
        if len(rows) < 2:
            continue
        last = rows[0].booking_date
        gap = (today - last).days
        if gap <= 45:
            continue
        findings.append(
            Finding(
                key=f"missing:{contract.id}:{last.isoformat()}",
                kind="missing",
                severity="warn",
                title=f"Zahlung fehlt: {contract.name}",
                message=(
                    f"Die letzte Abbuchung für {contract.name} war am {last:%d.%m.%Y}, "
                    f"also vor {gap} Tagen. Prüf, ob eine Rücklastschrift vorliegt "
                    "oder ob Umsätze fehlen."
                ),
                action_url=f"/vertraege/{contract.id}",
                contract_id=contract.id,
            )
        )
    return findings


def check_duplicates(session: Session, today: date) -> list[Finding]:
    """Mehrere aktive Verträge in derselben Kategorie."""
    findings = []
    buckets: dict[str, list[Contract]] = defaultdict(list)
    for contract in session.query(Contract).filter(Contract.status == "active").all():
        if contract.monthly_cents > 0 and contract.category:
            buckets[contract.category].append(contract)

    watch = {"Streaming & Medien", "Software & Cloud", "Sport & Fitness", "Mobilfunk & Internet"}
    for category, items in buckets.items():
        if category not in watch or len(items) < 2:
            continue
        total = sum(c.monthly_cents for c in items)
        names = ", ".join(c.name for c in items)
        findings.append(
            Finding(
                key=f"duplicate:{category}:{len(items)}",
                kind="duplicate",
                severity="info",
                title=f"{len(items)} Verträge in {category}",
                message=(
                    f"{names} - zusammen {format_cents(total)} im Monat "
                    f"({format_cents(total * 12)} im Jahr). "
                    "Nutzt du wirklich alle davon?"
                ),
                action_url=f"/vertraege?kategorie={category}",
            )
        )
    return findings


def check_budget(session: Session, today: date, income_hint_cents: int = 0) -> list[Finding]:
    """Wie viel vom Einkommen ist durch Fixkosten gebunden?"""
    costs = finance.fixed_costs(session)
    income = finance.average_monthly_income(session, today) or income_hint_cents
    if income <= 0 or costs.monthly_cents <= 0:
        return []
    ratio = costs.monthly_cents / income
    if ratio < 0.5:
        return []
    severity = "critical" if ratio >= 0.7 else "warn"
    return [
        Finding(
            key=f"budget:{today:%Y-%m}",
            kind="budget",
            severity=severity,
            title=f"Fixkosten binden {ratio * 100:.0f} % deiner Einnahmen",
            message=(
                f"{format_cents(costs.monthly_cents)} feste Kosten stehen "
                f"{format_cents(income)} Einnahmen im Monat gegenüber. "
                "Für Unerwartetes bleibt wenig Luft - die größten Posten findest du "
                "in der Vertragsübersicht."
            ),
            action_url="/vertraege",
        )
    ]

    # --------------------------------------------------------------------------- #
    # Alles zusammen
    # --------------------------------------------------------------------------- #


def collect(session: Session, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    lead = prefs.get_int(session, "reminder_lead_days", 45)
    income_hint = prefs.get_int(session, "monthly_income_hint", 0) * 100

    findings: list[Finding] = []
    findings += check_deadlines(session, today, lead)
    findings += check_untracked_subscriptions(session, today)
    findings += check_price_increases(session, today)
    findings += check_missing_payments(session, today)
    findings += check_duplicates(session, today)
    findings += check_budget(session, today, income_hint)
    findings += check_incomplete_contracts(session, today)

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), f.due_date or date.max))
    return findings


def refresh_alerts(session: Session, today: date | None = None) -> list[Alert]:
    """Schreibt die Hinweise in die Datenbank (bestehende bleiben erhalten)."""
    today = today or date.today()
    findings = collect(session, today)
    existing = {alert.key: alert for alert in session.query(Alert).all()}
    current_keys = set()

    for finding in findings:
        current_keys.add(finding.key)
        alert = existing.get(finding.key)
        if alert is None:
            alert = Alert(key=finding.key)
            session.add(alert)
        alert.kind = finding.kind
        alert.severity = finding.severity
        alert.title = finding.title
        alert.message = finding.message
        alert.action_url = finding.action_url
        alert.contract_id = finding.contract_id
        alert.due_date = finding.due_date

        # Hinweise, die sich erledigt haben, verschwinden wieder.
    for key, alert in existing.items():
        if key not in current_keys:
            session.delete(alert)

    session.flush()
    return (
        session.query(Alert)
        .filter(Alert.dismissed.is_(False))
        .order_by(Alert.due_date.is_(None), Alert.due_date)
        .all()
    )


def open_alerts(session: Session) -> list[Alert]:
    alerts = session.query(Alert).filter(Alert.dismissed.is_(False)).all()
    return sorted(
        alerts,
        key=lambda a: (SEVERITY_ORDER.get(a.severity, 3), a.due_date or date.max),
    )
