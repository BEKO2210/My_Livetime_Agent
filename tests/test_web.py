"""Durchklick-Tests: jede Seite muss ohne Daten und mit Daten funktionieren."""

from __future__ import annotations

from datetime import date


def test_startseite_ohne_daten(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "Lass uns starten" in antwort.text


def test_alle_seiten_erreichbar(client):
    for pfad in [
        "/",
        "/vertraege",
        "/vertraege/neu",
        "/finanzen",
        "/import",
        "/buddy",
        "/einstellungen",
    ]:
        antwort = client.get(pfad)
        assert antwort.status_code == 200, pfad


def test_vertrag_anlegen_bearbeiten_kuendigen(client):
    antwort = client.post(
        "/vertraege/neu",
        data={
            "name": "Netflix Standard",
            "provider": "Netflix",
            "kind": "abo",
            "category": "Streaming & Medien",
            "amount": "17,99",
            "interval": "monthly",
            "start_date": "2025-03-01",
            "minimum_term_months": "12",
            "renewal_months": "12",
            "notice_months": "1",
            "notice_days": "0",
            "reminder_lead_days": "",
            "customer_number": "K-123",
            "contact_email": "",
            "website": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert antwort.status_code == 200
    assert "Netflix Standard" in antwort.text
    assert "17,99" in antwort.text

    uebersicht = client.get("/vertraege")
    assert "Netflix Standard" in uebersicht.text

    brief = client.get("/vertraege/1/kuendigung")
    assert brief.status_code == 200
    assert "hiermit kündige ich" in brief.text
    assert "K-123" in brief.text

    client.post("/vertraege/1/status", data={"status": "cancelled"}, follow_redirects=True)
    detail = client.get("/vertraege/1")
    assert "gekündigt" in detail.text


def test_csv_import_und_auswertung(client):
    csv = (
        '"Buchungstag";"Beguenstigter/Zahlungspflichtiger";"Verwendungszweck";"Betrag"\n'
        '"01.09.2026";"NETFLIX INTERNATIONAL B.V.";"Abo";"-17,99"\n'
        '"01.09.2026";"ARBEITGEBER GMBH";"Gehalt";"2.850,00"\n'
    ).encode("utf-8")

    antwort = client.post(
        "/import",
        files={"datei": ("umsaetze.csv", csv, "text/csv")},
        data={"konto": "Giro"},
        follow_redirects=True,
    )
    assert antwort.status_code == 200
    assert "NETFLIX" in antwort.text.upper()

    export = client.get("/export/buchungen.csv")
    assert export.status_code == 200
    assert "NETFLIX" in export.content.decode("utf-8-sig").upper()

    daten = client.get("/export/daten.json").json()
    assert len(daten["buchungen"]) == 2


def test_import_einer_unbrauchbaren_datei_bricht_nicht_ab(client):
    antwort = client.post(
        "/import",
        files={"datei": ("kaputt.csv", b"nur text", "text/csv")},
        data={"konto": ""},
        follow_redirects=True,
    )
    assert antwort.status_code == 200
    assert "Spalten" in antwort.text or "gelesen" in antwort.text


def test_manuelle_buchung_und_zuordnung(client):
    client.post(
        "/vertraege/neu",
        data={
            "name": "Stromvertrag",
            "provider": "Stadtwerke",
            "category": "Energie",
            "amount": "85,00",
            "interval": "monthly",
            "start_date": "2024-01-01",
            "kind": "vertrag",
            "minimum_term_months": "0",
            "renewal_months": "0",
            "notice_months": "1",
            "notice_days": "0",
        },
        follow_redirects=True,
    )
    client.post(
        "/finanzen/neu",
        data={
            "booking_date": "2026-09-01",
            "amount": "85,00",
            "direction": "aus",
            "counterparty": "STADTWERKE",
            "purpose": "Abschlag",
            "category": "",
            "contract_id": "",
        },
        follow_redirects=True,
    )
    finanzen = client.get("/finanzen")
    assert "STADTWERKE" in finanzen.text
    assert "85,00" in finanzen.text


def test_einstellungen_speichern(client):
    antwort = client.post(
        "/einstellungen",
        data={
            "owner_name": "Belkis",
            "currency": "EUR",
            "reminder_lead_days": "30",
            "briefing_hour": "7",
            "notify_channel": "app",
            "theme": "dark",
            "monthly_income_hint": "2800",
        },
        follow_redirects=True,
    )
    assert antwort.status_code == 200
    seite = client.get("/einstellungen")
    assert 'value="Belkis"' in seite.text
    assert 'value="30"' in seite.text

    briefing = client.get("/briefing.txt")
    assert "Belkis" in briefing.text


def test_gesundheitscheck(client):
    daten = client.get("/gesundheit").json()
    assert daten["status"] == "ok"
    assert "vertraege" in daten


def test_buddy_erkennt_unbekanntes_abo(client):
    zeilen = ['"Buchungstag";"Beguenstigter/Zahlungspflichtiger";"Verwendungszweck";"Betrag"']
    for monat in range(1, 8):
        zeilen.append(f'"05.{monat:02d}.2026";"SPOTIFY AB";"Premium";"-10,99"')
    csv = ("\n".join(zeilen) + "\n").encode("utf-8")

    client.post(
        "/import",
        files={"datei": ("u.csv", csv, "text/csv")},
        data={"konto": ""},
        follow_redirects=True,
    )
    buddy = client.get("/buddy")
    assert buddy.status_code == 200
    assert "SPOTIFY" in buddy.text.upper()
    assert "aus_buchung" in buddy.text


def test_unbekannte_seite_leitet_freundlich_um(client):
    antwort = client.get("/vertraege/999", follow_redirects=True)
    assert antwort.status_code == 200
    assert "nicht gefunden" in antwort.text
