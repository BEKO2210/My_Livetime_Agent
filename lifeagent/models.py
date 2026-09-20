"""Datenmodell des Life Agent.

Bewusst flach gehalten: Vertrag, Buchung, Zuordnungsregel, Hinweis, Einstellung.
Alle Beträge in Cent (int), alle Daten als date.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .dates import INTERVAL_LABELS, Timing, monthly_cents, timing_for, yearly_cents


class Base(DeclarativeBase):
    pass

    # --------------------------------------------------------------------------- #
    # Auswahllisten für die Oberfläche
    # --------------------------------------------------------------------------- #


CONTRACT_KINDS: dict[str, str] = {
    "abo": "Abo",
    "vertrag": "Vertrag",
    "versicherung": "Versicherung",
    "mitgliedschaft": "Mitgliedschaft",
    "anmeldung": "Anmeldung / Konto",
    "kredit": "Kredit / Rate",
    "miete": "Miete / Wohnen",
}

CONTRACT_STATUS: dict[str, str] = {
    "active": "aktiv",
    "cancelled": "gekündigt",
    "paused": "pausiert",
    "ended": "beendet",
}

CATEGORIES: list[str] = [
    "Wohnen",
    "Energie",
    "Mobilfunk & Internet",
    "Streaming & Medien",
    "Software & Cloud",
    "Versicherung",
    "Gesundheit",
    "Mobilität",
    "Sport & Fitness",
    "Bildung",
    "Finanzen",
    "Familie & Kinder",
    "Lebensmittel",
    "Einkauf",
    "Gehalt",
    "Nebeneinkommen",
    "Sonstiges",
]


# --------------------------------------------------------------------------- #
# Tabellen
# --------------------------------------------------------------------------- #


class Contract(Base):
    """Ein Vertrag, Abo, eine Versicherung oder eine Anmeldung."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(160), default="")
    kind: Mapped[str] = mapped_column(String(32), default="abo")
    category: Mapped[str] = mapped_column(String(64), default="Sonstiges")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)

    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    interval: Mapped[str] = mapped_column(String(16), default="monthly")

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    minimum_term_months: Mapped[int] = mapped_column(Integer, default=0)
    renewal_months: Mapped[int] = mapped_column(Integer, default=0)
    notice_months: Mapped[int] = mapped_column(Integer, default=0)
    notice_days: Mapped[int] = mapped_column(Integer, default=0)
    reminder_lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    customer_number: Mapped[str] = mapped_column(String(120), default="")
    contact_email: Mapped[str] = mapped_column(String(160), default="")
    website: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    cancelled_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="contract", cascade="save-update"
    )
    rules: Mapped[list["MatchRule"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )

    # -- abgeleitete Werte -------------------------------------------------- #

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "paused")

    @property
    def counts_as_cost(self) -> bool:
        return self.status == "active" and self.amount_cents > 0

    @property
    def interval_label(self) -> str:
        return INTERVAL_LABELS.get(self.interval, self.interval)

    @property
    def kind_label(self) -> str:
        return CONTRACT_KINDS.get(self.kind, self.kind)

    @property
    def status_label(self) -> str:
        return CONTRACT_STATUS.get(self.status, self.status)

    @property
    def monthly_cents(self) -> int:
        return monthly_cents(self.amount_cents, self.interval)

    @property
    def yearly_cents(self) -> int:
        return yearly_cents(self.amount_cents, self.interval)

    def timing(self, today: date | None = None) -> Timing:
        return timing_for(
            start=self.start_date,
            interval=self.interval,
            minimum_term_months=self.minimum_term_months,
            renewal_months=self.renewal_months,
            notice_months=self.notice_months,
            notice_days=self.notice_days,
            end_date=self.end_date,
            today=today,
        )

    def lead_days(self, fallback: int = 45) -> int:
        return self.reminder_lead_days if self.reminder_lead_days is not None else fallback

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contract {self.id} {self.name!r} {self.amount_cents}>"


class Transaction(Base):
    """Eine Buchung: Einnahme (positiv) oder Ausgabe (negativ)."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_transaction_fingerprint"),
        Index("ix_transaction_date", "booking_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    counterparty: Mapped[str] = mapped_column(String(200), default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    account: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(24), default="manuell")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contract: Mapped[Contract | None] = relationship(back_populates="transactions")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def is_income(self) -> bool:
        return self.amount_cents > 0

    @property
    def label(self) -> str:
        return self.counterparty or self.purpose[:60] or "Buchung"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Transaction {self.booking_date} {self.amount_cents} {self.counterparty!r}>"


class MatchRule(Base):
    """Merkregel: Text im Empfänger/Verwendungszweck -> Vertrag bzw. Kategorie."""

    __tablename__ = "match_rules"
    __table_args__ = (UniqueConstraint("pattern", name="uq_rule_pattern"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="")
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True
    )
    contract: Mapped[Contract | None] = relationship(back_populates="rules")
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Alert(Base):
    """Ein Hinweis des Buddys ("du zahlst zweimal für Streaming")."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("key", name="uq_alert_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info|warn|critical
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    action_url: Mapped[str] = mapped_column(String(300), default="")
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    @property
    def severity_label(self) -> str:
        return {"critical": "dringend", "warn": "wichtig", "info": "Hinweis"}.get(
            self.severity, self.severity
        )


class Setting(Base):
    """Schlüssel/Wert-Einstellungen, die in der Oberfläche änderbar sind."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
