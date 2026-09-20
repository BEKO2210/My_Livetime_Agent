from datetime import date

from lifeagent.dates import add_months
from lifeagent.models import Contract
from lifeagent.services import insights
from lifeagent.services.ledger import add_transaction

HEUTE = date(2026, 6, 15)


def _abo(session, name, betrag, counterparty, monate=8, ab_monat=1, contract_id=None):
    for offset in range(monate, 0, -1):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=5), -offset),
            amount_cents=-betrag,
            counterparty=counterparty,
            purpose=name,
            contract_id=contract_id,
        )


def test_frist_wird_gemeldet(session):
    # Mindestlaufzeit endet in gut drei Wochen, Frist zwei Wochen vorher
    session.add(
        Contract(
            name="Mobilfunk",
            category="Mobilfunk & Internet",
            amount_cents=3999,
            interval="monthly",
            start_date=date(2024, 8, 10),
            minimum_term_months=24,
            renewal_months=12,
            notice_months=0,
            notice_days=30,
        )
    )
    session.flush()
    befunde = insights.collect(session, HEUTE)
    fristen = [f for f in befunde if f.kind == "deadline"]
    assert len(fristen) == 1
    # Laufzeitende 09.08.2026, 30 Tage Frist -> spaetestens am 10.07.2026 kuendigen
    assert fristen[0].due_date == date(2026, 7, 10)
    assert fristen[0].severity == "warn"


def test_unbekanntes_abo_wird_gefunden(session):
    _abo(session, "Premium", 1099, "SPOTIFY AB")
    session.flush()
    befunde = [f for f in insights.collect(session, HEUTE) if f.kind == "untracked"]
    assert len(befunde) == 1
    assert "SPOTIFY" in befunde[0].title.upper()


def test_bekanntes_abo_wird_nicht_gemeldet(session):
    contract = Contract(name="Spotify", provider="Spotify", amount_cents=1099, interval="monthly")
    session.add(contract)
    session.flush()
    _abo(session, "Premium", 1099, "SPOTIFY AB", contract_id=contract.id)
    session.flush()
    assert [f for f in insights.collect(session, HEUTE) if f.kind == "untracked"] == []


def test_einkaeufe_gelten_nicht_als_abo(session):
    for offset, betrag in enumerate([6540, 4210, 7830, 3120, 9900, 2250], start=1):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=12), -offset),
            amount_cents=-betrag,
            counterparty="REWE MARKT",
            purpose="Einkauf",
        )
    session.flush()
    assert [f for f in insights.collect(session, HEUTE) if f.kind == "untracked"] == []


def test_preiserhoehung_wird_erkannt(session):
    for offset in range(8, 3, -1):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=5), -offset),
            amount_cents=-1399,
            counterparty="NETFLIX INTERNATIONAL B.V.",
            purpose="Abo",
        )
    for offset in range(3, 0, -1):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=5), -offset),
            amount_cents=-1799,
            counterparty="NETFLIX INTERNATIONAL B.V.",
            purpose="Abo",
        )
    session.flush()
    preise = [f for f in insights.collect(session, HEUTE) if f.kind == "price"]
    assert len(preise) == 1
    assert "17,99" in preise[0].message


def test_doppelte_kategorie(session):
    session.add_all(
        [
            Contract(
                name="Netflix", category="Streaming & Medien", amount_cents=1399, interval="monthly"
            ),
            Contract(
                name="Disney+", category="Streaming & Medien", amount_cents=899, interval="monthly"
            ),
        ]
    )
    session.flush()
    doppelte = [f for f in insights.collect(session, HEUTE) if f.kind == "duplicate"]
    assert len(doppelte) == 1
    assert "Netflix" in doppelte[0].message


def test_fehlende_zahlung(session):
    contract = Contract(
        name="Fitness", category="Sport & Fitness", amount_cents=2999, interval="monthly"
    )
    session.add(contract)
    session.flush()
    for offset in (8, 7, 6, 5, 4, 3):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=7), -offset),
            amount_cents=-2999,
            counterparty="FITX",
            purpose="Beitrag",
            contract_id=contract.id,
        )
    session.flush()
    fehlend = [f for f in insights.collect(session, HEUTE) if f.kind == "missing"]
    assert len(fehlend) == 1


def test_fixkostenquote(session):
    session.add(Contract(name="Miete", category="Wohnen", amount_cents=120000, interval="monthly"))
    session.flush()
    for offset in (1, 2, 3):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=1), -offset),
            amount_cents=150000,
            counterparty="ARBEITGEBER",
            purpose="Gehalt",
        )
    session.flush()
    budget = [f for f in insights.collect(session, HEUTE) if f.kind == "budget"]
    assert len(budget) == 1
    assert budget[0].severity == "critical"


def test_fehlender_vertragsbeginn_wird_angemahnt(session):
    session.add(Contract(name="Irgendwas", amount_cents=500, interval="monthly"))
    session.flush()
    unvollstaendig = [f for f in insights.collect(session, HEUTE) if f.kind == "incomplete"]
    assert len(unvollstaendig) == 1


def test_hinweise_werden_gespeichert_und_verschwinden_wieder(session):
    contract = Contract(
        name="Test",
        category="Streaming & Medien",
        amount_cents=999,
        interval="monthly",
        start_date=date(2025, 1, 1),
        minimum_term_months=12,
        renewal_months=12,
        notice_months=1,
    )
    session.add(contract)
    session.flush()

    erste = insights.refresh_alerts(session, date(2025, 11, 20))
    assert any(a.kind == "deadline" for a in erste)

    # Vertrag gekuendigt -> Hinweis faellt weg
    contract.status = "cancelled"
    session.flush()
    zweite = insights.refresh_alerts(session, date(2025, 11, 21))
    assert not any(a.kind == "deadline" for a in zweite)


def test_supermarkt_ist_kein_abo_kandidat(session):
    for offset in range(6, 0, -1):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=12), -offset),
            amount_cents=-6540,
            counterparty="REWE MARKT",
            purpose="Einkauf",
            category="Lebensmittel",
        )
    session.flush()
    gruppen = insights.recurring_groups(session, HEUTE)
    assert gruppen and all(not g.is_subscription_candidate for g in gruppen)


def test_letzter_betrag_wird_gemerkt(session):
    for offset, betrag in ((3, 1399), (2, 1399), (1, 1799)):
        add_transaction(
            session,
            booking_date=add_months(HEUTE.replace(day=5), -offset),
            amount_cents=-betrag,
            counterparty="NETFLIX",
            purpose="Abo",
        )
    session.flush()
    gruppe = insights.recurring_groups(session, HEUTE)[0]
    assert gruppe.latest_amount == 1799
    assert gruppe.typical_amount == 1399
