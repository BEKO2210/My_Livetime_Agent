from datetime import date

import pytest

from lifeagent.dates import (
    add_months,
    cancel_deadline,
    earliest_exit,
    monthly_cents,
    next_due,
    parse_date,
    term_end,
    timing_for,
    yearly_cents,
)

HEUTE = date(2026, 6, 15)


def test_add_months_klemmt_monatsende():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # Schaltjahr
    assert add_months(date(2026, 3, 15), -3) == date(2025, 12, 15)


def test_laufzeit_24_monate_mit_verlaengerung():
    # Start 01.03.2024, 24 Monate Mindestlaufzeit -> Ende 28.02.2026,
    # danach 12 Monate Verlaengerung -> 28.02.2027
    ende = term_end(date(2024, 3, 1), 24, 12, HEUTE)
    assert ende == date(2027, 2, 28)
    assert cancel_deadline(ende, notice_months=3) == date(2026, 11, 28)


def test_unbefristeter_vertrag_hat_keine_periode():
    assert term_end(date(2025, 1, 15), 0, 0, HEUTE) is None
    timing = timing_for(date(2025, 1, 15), "monthly", notice_months=1, today=HEUTE)
    assert timing.open_ended is True
    assert timing.cancel_by is None


def test_mindestlaufzeit_ohne_verlaengerung_laeuft_danach_unbefristet():
    # 12 Monate Mindestlaufzeit ab 2024 -> laengst vorbei -> unbefristet
    assert term_end(date(2024, 1, 1), 12, 0, HEUTE) is None
    # noch laufende Mindestlaufzeit wird zurueckgegeben
    assert term_end(date(2026, 1, 1), 12, 0, HEUTE) == date(2026, 12, 31)


def test_frist_in_tagen():
    ende = date(2026, 7, 31)
    assert cancel_deadline(ende, notice_days=30) == date(2026, 7, 1)
    assert cancel_deadline(None, notice_months=3) is None


def test_fruehester_ausstieg():
    assert earliest_exit(HEUTE, notice_months=1) == date(2026, 7, 15)


@pytest.mark.parametrize(
    "interval,erwartet",
    [("monthly", date(2026, 7, 5)), ("yearly", date(2027, 1, 5)), ("quarterly", date(2026, 7, 5))],
)
def test_naechste_zahlung(interval, erwartet):
    assert next_due(date(2025, 1, 5), interval, HEUTE) == erwartet


def test_einmalzahlung_in_der_vergangenheit():
    assert next_due(date(2025, 1, 5), "once", HEUTE) is None


def test_umrechnung_auf_monat_und_jahr():
    assert monthly_cents(12000, "yearly") == 1000
    assert monthly_cents(3000, "quarterly") == 1000
    assert monthly_cents(1000, "weekly") == 4333
    assert monthly_cents(5000, "once") == 0
    assert yearly_cents(1000, "monthly") == 12000


def test_dringlichkeit():
    bald = timing_for(date(2025, 8, 1), "monthly", 12, 12, 1, today=date(2026, 6, 25))
    assert bald.cancel_by == date(2026, 6, 30)
    assert bald.urgency == "critical"


def test_datum_lesen():
    assert parse_date("01.03.2024") == date(2024, 3, 1)
    assert parse_date("2024-03-01") == date(2024, 3, 1)
    assert parse_date("Unsinn") is None
    assert parse_date("") is None
