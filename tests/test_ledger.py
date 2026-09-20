from datetime import date

from lifeagent.models import Contract, MatchRule, Transaction
from lifeagent.services import matching
from lifeagent.services.importer import parse_csv
from lifeagent.services.ledger import add_transaction, save_import

CSV = (
    '"Buchungstag";"Beguenstigter/Zahlungspflichtiger";"Verwendungszweck";"Betrag"\n'
    '"01.09.2026";"NETFLIX INTERNATIONAL B.V.";"Abo";"-17,99"\n'
    '"02.09.2026";"REWE MARKT GMBH";"Einkauf";"-45,30"\n'
).encode("utf-8")


def test_import_legt_buchungen_an_und_ueberspringt_doppelte(session):
    ergebnis = save_import(session, parse_csv(CSV), account="Giro")
    assert ergebnis.imported == 2

    nochmal = save_import(session, parse_csv(CSV), account="Giro")
    assert nochmal.imported == 0
    assert nochmal.duplicates == 2
    assert session.query(Transaction).count() == 2


def test_eingebautes_wissen_setzt_kategorie(session):
    save_import(session, parse_csv(CSV))
    netflix = session.query(Transaction).filter(Transaction.amount_cents == -1799).one()
    rewe = session.query(Transaction).filter(Transaction.amount_cents == -4530).one()
    assert netflix.category == "Streaming & Medien"
    assert rewe.category == "Lebensmittel"


def test_vertragsname_wird_erkannt(session):
    session.add(
        Contract(name="Netflix Standard", provider="Netflix", category="Streaming & Medien")
    )
    session.flush()
    save_import(session, parse_csv(CSV))
    netflix = session.query(Transaction).filter(Transaction.amount_cents == -1799).one()
    assert netflix.contract is not None
    assert netflix.contract.name == "Netflix Standard"


def test_gelernte_regel_greift_beim_naechsten_import(session):
    contract = Contract(name="Wocheneinkauf", provider="", category="Lebensmittel")
    session.add(contract)
    session.flush()

    buchung = add_transaction(
        session,
        booking_date=date(2026, 8, 2),
        amount_cents=-4530,
        counterparty="REWE MARKT GMBH",
        purpose="Einkauf",
    )
    matching.learn_rule(session, buchung, contract.id, "Lebensmittel")
    session.flush()
    assert session.query(MatchRule).count() == 1

    save_import(session, parse_csv(CSV))
    neue = session.query(Transaction).filter(Transaction.booking_date == date(2026, 9, 2)).one()
    assert neue.contract_id == contract.id


def test_manuelle_buchung_wird_nicht_doppelt_angelegt(session):
    erste = add_transaction(
        session, booking_date=date(2026, 9, 1), amount_cents=-1000, counterparty="Test"
    )
    zweite = add_transaction(
        session, booking_date=date(2026, 9, 1), amount_cents=-1000, counterparty="Test"
    )
    assert erste is not None
    assert zweite is None


def test_nachtraegliche_zuordnung(session):
    add_transaction(
        session,
        booking_date=date(2026, 9, 5),
        amount_cents=-2999,
        counterparty="FITX GMBH",
        purpose="Beitrag",
    )
    session.add(Contract(name="Fitnessstudio", provider="FitX", category="Sport & Fitness"))
    session.flush()
    geaendert = matching.rematch_all(session, only_unassigned=True)
    assert geaendert == 1
