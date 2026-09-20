import pytest

from lifeagent.money import format_cents, to_cents


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12,99", 1299),
        ("-12,99", -1299),
        ("1.234,56", 123456),
        ("1,234.56", 123456),
        ("12.99", 1299),
        ("1234", 123400),
        ("12,99-", -1299),  # nachgestelltes Minus wie in Bank-Exporten
        ("  89,00 EUR ", 8900),
        ("", 0),
        (None, 0),
        ("0,00", 0),
        ("9,5", 950),
        ("+45,10", 4510),
    ],
)
def test_betraege_lesen(value, expected):
    assert to_cents(value) == expected


def test_formatierung_ist_deutsch():
    assert format_cents(123456) == "1.234,56 €"
    assert format_cents(-1299) == "-12,99 €"
    assert format_cents(1299, signed=True) == "+12,99 €"
    assert format_cents(None) == "-"


def test_rundung_kaufmaennisch():
    assert to_cents("0,005") == 1
    assert to_cents(19.995) == 2000
