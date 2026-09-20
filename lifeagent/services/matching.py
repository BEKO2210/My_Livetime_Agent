"""Buchungen den richtigen Verträgen und Kategorien zuordnen."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import Contract, MatchRule, Transaction
from . import knowledge

_NOISE = re.compile(
    r"(gmbh|ag|kg|se|b\.?v\.?|ltd|inc|co\.?|deutschland|international|\bag\b)", re.I
)


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = _NOISE.sub(" ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def signature(counterparty: str, purpose: str) -> str:
    """Kurzer Erkennungsschlüssel für wiederkehrende Zahlungen."""
    base = normalize(counterparty) or normalize(purpose)
    words = [w for w in base.split() if len(w) > 2 and not w.isdigit()]
    return " ".join(words[:3])


@dataclass
class MatchOutcome:
    contract_id: int | None = None
    category: str = ""
    rule_id: int | None = None
    confidence: str = "none"  # rule | contract | knowledge | none


def match_transaction(
    session: Session,
    counterparty: str,
    purpose: str,
    amount_cents: int = 0,
) -> MatchOutcome:
    """Reihenfolge: gelernte Regel -> Vertragsname -> eingebautes Wissen."""
    haystack = normalize(f"{counterparty} {purpose}")

    if haystack:
        for rule in session.query(MatchRule).order_by(MatchRule.hits.desc()).all():
            pattern = normalize(rule.pattern)
            if pattern and pattern in haystack:
                return MatchOutcome(
                    contract_id=rule.contract_id,
                    category=rule.category or "",
                    rule_id=rule.id,
                    confidence="rule",
                )

        for contract in session.query(Contract).all():
            for candidate in (contract.provider, contract.name):
                token = normalize(candidate)
                if len(token) >= 3 and token in haystack:
                    return MatchOutcome(
                        contract_id=contract.id,
                        category=contract.category,
                        confidence="contract",
                    )

    category = knowledge.suggest_category(counterparty, purpose, amount_cents)
    if category:
        return MatchOutcome(category=category, confidence="knowledge")
    return MatchOutcome()


def apply_match(session: Session, transaction: Transaction, outcome: MatchOutcome) -> None:
    if outcome.contract_id and not transaction.contract_id:
        transaction.contract_id = outcome.contract_id
    if outcome.category and not transaction.category:
        transaction.category = outcome.category
    if outcome.rule_id:
        rule = session.get(MatchRule, outcome.rule_id)
        if rule:
            rule.hits = (rule.hits or 0) + 1


def learn_rule(
    session: Session,
    transaction: Transaction,
    contract_id: int | None,
    category: str = "",
) -> MatchRule | None:
    """Merkt sich die Zuordnung, damit sie beim nächsten Import automatisch greift."""
    pattern = signature(transaction.counterparty, transaction.purpose)
    if len(pattern) < 3:
        return None
    existing = session.query(MatchRule).filter(MatchRule.pattern == pattern).one_or_none()
    if existing:
        existing.contract_id = contract_id
        if category:
            existing.category = category
        return existing
    rule = MatchRule(pattern=pattern, contract_id=contract_id, category=category or "")
    session.add(rule)
    return rule


def rematch_all(session: Session, only_unassigned: bool = True) -> int:
    """Wendet Regeln und Wissen erneut auf vorhandene Buchungen an."""
    query = session.query(Transaction)
    if only_unassigned:
        query = query.filter(Transaction.contract_id.is_(None))
    changed = 0
    for transaction in query.all():
        before = (transaction.contract_id, transaction.category)
        outcome = match_transaction(
            session, transaction.counterparty, transaction.purpose, transaction.amount_cents
        )
        apply_match(session, transaction, outcome)
        if (transaction.contract_id, transaction.category) != before:
            changed += 1
    return changed
