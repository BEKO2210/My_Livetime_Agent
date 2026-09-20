from datetime import date

from lifeagent.services.importer import parse_csv

SPARKASSE = (
    '"Auftragskonto";"Buchungstag";"Valutadatum";"Buchungstext";"Verwendungszweck";'
    '"Beguenstigter/Zahlungspflichtiger";"Betrag";"Waehrung"\n'
    '"DE12";"01.09.2026";"01.09.2026";"LASTSCHRIFT";"Netflix Abo 09/2026";'
    '"NETFLIX INTERNATIONAL B.V.";"-17,99";"EUR"\n'
    '"DE12";"01.09.2026";"01.09.2026";"GUTSCHRIFT";"Gehalt September";'
    '"ARBEITGEBER GMBH";"2.850,00";"EUR"\n'
).encode("utf-8")

DKB_MIT_VORSPANN = (
    "Kontonummer:;DE00 1111 2222\n"
    "Zeitraum:;01.09.2026 - 30.09.2026\n"
    "\n"
    '"Buchungstag";"Wertstellung";"Buchungstext";"Auftraggeber / Beguenstigter";'
    '"Verwendungszweck";"Betrag (EUR)"\n'
    '"05.09.2026";"05.09.2026";"Lastschrift";"SPOTIFY AB";"Premium";"-10,99"\n'
).encode("cp1252")

KOMMA_GETRENNT = (
    "Date,Amount,Payee,Description\n" "2026-09-07,-12.50,Hetzner Online,Server\n"
).encode("utf-8")


def test_sparkasse_format():
    result = parse_csv(SPARKASSE, account="Giro")
    assert result.count == 2
    assert result.problems == []
    ausgabe, einnahme = result.rows
    assert ausgabe.booking_date == date(2026, 9, 1)
    assert ausgabe.amount_cents == -1799
    assert ausgabe.counterparty == "NETFLIX INTERNATIONAL B.V."
    assert einnahme.amount_cents == 285000


def test_vorspann_wird_uebersprungen():
    result = parse_csv(DKB_MIT_VORSPANN)
    assert result.count == 1
    assert result.rows[0].counterparty == "SPOTIFY AB"
    assert result.rows[0].amount_cents == -1099


def test_englisches_format_mit_komma_trenner():
    result = parse_csv(KOMMA_GETRENNT)
    assert result.delimiter == ","
    assert result.count == 1
    assert result.rows[0].amount_cents == -1250
    assert result.rows[0].counterparty == "Hetzner Online"


def test_doppelte_zeilen_in_einer_datei():
    doppelt = SPARKASSE + SPARKASSE.split(b"\n", 1)[1]
    result = parse_csv(doppelt)
    assert result.count == 2
    assert result.skipped >= 2


def test_unbrauchbare_datei_meldet_klar():
    result = parse_csv(b"nur irgendein Text ohne Struktur\n")
    assert result.count == 0
    assert result.problems


def test_leere_datei():
    result = parse_csv(b"")
    assert result.count == 0
    assert result.problems


def test_fingerabdruck_ist_stabil():
    erste = parse_csv(SPARKASSE).rows[0]
    zweite = parse_csv(SPARKASSE).rows[0]
    assert erste.fingerprint == zweite.fingerprint
