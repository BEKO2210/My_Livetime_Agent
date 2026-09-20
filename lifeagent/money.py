"""Geldbeträge. Intern immer in Cent (int), nie als float."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

_AMOUNT_CLEAN = re.compile(r"[^\d,.\-+]")


def _looks_like_thousands(head: str, tail: str, separator: str) -> bool:
    """Ist das Trennzeichen ein Tausenderpunkt/-komma und kein Dezimaltrenner?"""
    if len(tail) != 3 or not head or separator in head:
        return False
    if head == "0" or head.startswith("0"):
        return False  # "0,005" ist ein Dezimalwert, kein Tausenderblock
    return head.isdigit()


def to_cents(value) -> int:
    """Wandelt eine Zahl oder einen String in Cent um.

    Versteht deutsche ("1.234,56") und englische ("1,234.56") Schreibweise
    sowie nachgestellte Vorzeichen ("12,99-") wie in Bank-Exporten üblich.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        return int((Decimal(str(value)) * 100).quantize(Decimal("1"), ROUND_HALF_UP))
    if isinstance(value, Decimal):
        return int((value * 100).quantize(Decimal("1"), ROUND_HALF_UP))

    text = str(value).strip()
    negative = False
    if text.endswith("-"):
        negative = True
        text = text[:-1]
    text = _AMOUNT_CLEAN.sub("", text)
    if not text:
        return 0
    if text.startswith("-"):
        negative = True
        text = text[1:]
    text = text.lstrip("+")

    if "," in text and "." in text:
        # Das letzte Trennzeichen ist das Dezimaltrennzeichen.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # "1,5" -> Dezimal. "1,234" ist englische Tausenderschreibweise,
        # "0,005" dagegen ein echter Dezimalwert - daher die Prüfung auf die führende Null.
        head, _, tail = text.rpartition(",")
        if _looks_like_thousands(head, tail, ","):
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    else:
        head, _, tail = text.rpartition(".")
        if _looks_like_thousands(head, tail, "."):
            text = text.replace(".", "")

    if not text or text == ".":
        return 0
    cents = int((Decimal(text) * 100).quantize(Decimal("1"), ROUND_HALF_UP))
    return -cents if negative else cents


def format_cents(cents: int | None, currency: str = "EUR", signed: bool = False) -> str:
    """Formatiert Cent als deutsche Währungsangabe: 1.234,56 EUR."""
    if cents is None:
        return "-"
    symbol = {"EUR": "€", "CHF": "CHF", "USD": "$"}.get(currency, currency)
    sign = "-" if cents < 0 else ("+" if signed and cents > 0 else "")
    whole, rest = divmod(abs(int(cents)), 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"{sign}{grouped},{rest:02d} {symbol}"


def split_amount(cents: int, parts: int) -> int:
    """Teilt einen Betrag kaufmännisch gerundet."""
    if parts <= 0:
        return 0
    return int((Decimal(cents) / parts).quantize(Decimal("1"), ROUND_HALF_UP))
