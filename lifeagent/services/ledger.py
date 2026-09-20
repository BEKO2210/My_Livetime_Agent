"""Buchungen speichern - manuell erfasst oder aus einer CSV importiert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..models import Transaction
from .importer import ImportResult, ParsedRow, fingerprint
from .matching import apply_match, match_transaction


@dataclass
class SaveReport:
    imported: int = 0
    duplicates: int = 0
    matched: int = 0
    problems: list[str] | None = None

    def as_text(self) -> str:
        parts = [f"{self.imported} Buchungen übernommen"]
        if self.duplicates:
            parts.append(f"{self.duplicates} doppelte übersprungen")
        if self.matched:
            parts.append(f"{self.matched} automatisch zugeordnet")
        return ", ".join(parts) + "."


def add_transaction(
    session: Session,
    booking_date: date,
    amount_cents: int,
    counterparty: str = "",
    purpose: str = "",
    category: str = "",
    contract_id: int | None = None,
    account: str = "",
    source: str = "manuell",
) -> Transaction | None:
    """Legt eine Buchung an. Gibt None zurück, wenn sie schon existiert."""
    mark = fingerprint(booking_date, amount_cents, counterparty, purpose)
    existing = session.query(Transaction).filter(Transaction.fingerprint == mark).one_or_none()
    if existing is not None:
        return None

    transaction = Transaction(
        booking_date=booking_date,
        amount_cents=amount_cents,
        counterparty=counterparty.strip(),
        purpose=purpose.strip(),
        category=category,
        contract_id=contract_id,
        account=account,
        source=source,
        fingerprint=mark,
    )
    session.add(transaction)

    if contract_id is None or not category:
        outcome = match_transaction(session, counterparty, purpose, amount_cents)
        apply_match(session, transaction, outcome)

    session.flush()
    return transaction


def save_import(session: Session, result: ImportResult, account: str = "") -> SaveReport:
    report = SaveReport(problems=list(result.problems))
    for row in result.rows:
        transaction = _save_row(session, row, account)
        if transaction is None:
            report.duplicates += 1
            continue
        report.imported += 1
        if transaction.contract_id or transaction.category:
            report.matched += 1
    session.flush()
    return report


def _save_row(session: Session, row: ParsedRow, account: str) -> Transaction | None:
    return add_transaction(
        session,
        booking_date=row.booking_date,
        amount_cents=row.amount_cents,
        counterparty=row.counterparty,
        purpose=row.purpose,
        account=account or row.account,
        source="import",
    )
