"""CSV-Import von Kontoumsätzen.

Ziel: der Nutzer laedt den Export seiner Bank hoch und es funktioniert -
ohne Spalten zuzuordnen. Getestet gegen die gängigen deutschen Formate
(Sparkasse, DKB, ING, Comdirect, N26) und generische Exporte.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date

from ..dates import parse_date
from ..money import to_cents

# Mögliche Spaltennamen, klein geschrieben und ohne Sonderzeichen verglichen.
DATE_HEADERS = (
    "buchungstag",
    "buchungsdatum",
    "belegdatum",
    "datum",
    "valuta",
    "valutadatum",
    "wertstellung",
    "date",
    "booking date",
)
AMOUNT_HEADERS = (
    "betrag",
    "betrag (eur)",
    "betrag eur",
    "umsatz",
    "amount",
    "value",
    "soll/haben betrag",
    "betrag in eur",
)
PARTNER_HEADERS = (
    "beguenstigter/zahlungspflichtiger",
    "beguenstigter",
    "zahlungsbeteiligter",
    "auftraggeber/empfaenger",
    "auftraggeber",
    "empfaenger",
    "name",
    "payee",
    "partnername",
    "zahlungspflichtiger",
    "beguenstigter/auftraggeber",
)
PURPOSE_HEADERS = (
    "verwendungszweck",
    "buchungstext",
    "vorgang/verwendungszweck",
    "vorgang",
    "referenz",
    "description",
    "beschreibung",
    "verwendungszweck (gekuerzt)",
)
CURRENCY_HEADERS = ("waehrung", "currency", "waehrung betrag")


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("﻿", "")
    )
    return re.sub(r"\s+", " ", text).strip(' "')


def _pick(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    normalized = [_norm(h) for h in headers]
    for candidate in candidates:
        if candidate in normalized:
            return normalized.index(candidate)
    for index, header in enumerate(normalized):
        if any(candidate in header for candidate in candidates):
            return index
    return None


def fingerprint(booking_date: date, amount_cents: int, counterparty: str, purpose: str) -> str:
    """Stabiler Fingerabdruck, damit derselbe Umsatz nicht doppelt landet."""
    raw = "|".join(
        [
            booking_date.isoformat(),
            str(amount_cents),
            _norm(counterparty)[:80],
            _norm(purpose)[:120],
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


@dataclass
class ParsedRow:
    booking_date: date
    amount_cents: int
    counterparty: str = ""
    purpose: str = ""
    account: str = ""

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.booking_date, self.amount_cents, self.counterparty, self.purpose)


@dataclass
class ImportResult:
    rows: list[ParsedRow] = field(default_factory=list)
    skipped: int = 0
    problems: list[str] = field(default_factory=list)
    delimiter: str = ";"
    encoding: str = "utf-8"

    @property
    def count(self) -> int:
        return len(self.rows)


def decode(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1"


def sniff_delimiter(sample: str) -> str:
    counts = {d: sample.count(d) for d in (";", ",", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ";"


def _find_header_row(rows: list[list[str]]) -> int:
    """Bank-Exporte haben oft Vorspann-Zeilen. Wir suchen die echte Kopfzeile."""
    for index, row in enumerate(rows[:25]):
        if len(row) < 2:
            continue
        if _pick(row, DATE_HEADERS) is not None and _pick(row, AMOUNT_HEADERS) is not None:
            return index
    return 0


def parse_csv(data: bytes, account: str = "") -> ImportResult:
    text, encoding = decode(data)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    delimiter = sniff_delimiter("\n".join(text.split("\n")[:15]))
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, quotechar='"')
    raw_rows = [row for row in reader if any((cell or "").strip() for cell in row)]

    result = ImportResult(delimiter=delimiter, encoding=encoding)
    if not raw_rows:
        result.problems.append("Die Datei enthält keine Daten.")
        return result

    header_index = _find_header_row(raw_rows)
    headers = raw_rows[header_index]
    body = raw_rows[header_index + 1 :]

    idx_date = _pick(headers, DATE_HEADERS)
    idx_amount = _pick(headers, AMOUNT_HEADERS)
    idx_partner = _pick(headers, PARTNER_HEADERS)
    idx_purpose = _pick(headers, PURPOSE_HEADERS)

    if idx_date is None or idx_amount is None:
        result.problems.append(
            "Ich habe keine Spalten für Datum und Betrag gefunden. "
            "Erwartet werden z.B. 'Buchungstag' und 'Betrag'."
        )
        return result

    seen: set[str] = set()
    for row in body:
        if len(row) <= max(idx_date, idx_amount):
            result.skipped += 1
            continue
        booking_date = parse_date(row[idx_date])
        if booking_date is None:
            result.skipped += 1
            continue
        amount = to_cents(row[idx_amount])
        if amount == 0:
            result.skipped += 1
            continue

        def cell(index: int | None) -> str:
            if index is None or index >= len(row):
                return ""
            return re.sub(r"\s+", " ", (row[index] or "").strip())

        parsed = ParsedRow(
            booking_date=booking_date,
            amount_cents=amount,
            counterparty=cell(idx_partner)[:200],
            purpose=cell(idx_purpose)[:500],
            account=account,
        )
        if parsed.fingerprint in seen:
            result.skipped += 1
            continue
        seen.add(parsed.fingerprint)
        result.rows.append(parsed)

    if not result.rows:
        result.problems.append("Es konnten keine Buchungen gelesen werden.")
    return result
