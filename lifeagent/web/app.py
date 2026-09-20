"""FastAPI-Anwendung: alle Seiten des Life Agent.

Server-gerendertes HTML, kein Build-Schritt, keine Anmeldung. Die App läuft
lokal auf dem Rechner des Nutzers - die Daten bleiben dort.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import APP_NAME, __version__
from ..dates import INTERVAL_LABELS, parse_date
from ..db import get_session_factory, init_db
from ..models import (
    CATEGORIES,
    CONTRACT_KINDS,
    CONTRACT_STATUS,
    Alert,
    Contract,
    MatchRule,
    Transaction,
)
from ..money import format_cents, to_cents
from ..services import briefing as briefing_service
from ..services import finance, insights, knowledge, ledger, letters, matching, notify, prefs
from ..services.importer import parse_csv

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --------------------------------------------------------------------------- #
# Hilfsfunktionen für die Templates
# --------------------------------------------------------------------------- #


def _money(cents, signed: bool = False) -> str:
    return format_cents(cents or 0, signed=signed)


def _date_de(value) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    return f"{value:%d.%m.%Y}"


def _days_label(days) -> str:
    if days is None:
        return ""
    if days < 0:
        return f"vor {abs(days)} Tagen"
    if days == 0:
        return "heute"
    if days == 1:
        return "morgen"
    return f"in {days} Tagen"


templates.env.filters["money"] = _money
templates.env.filters["datum"] = _date_de
templates.env.filters["tage"] = _days_label

templates.env.globals.update(
    app_name=APP_NAME,
    version=__version__,
    categories=CATEGORIES,
    kinds=CONTRACT_KINDS,
    statuses=CONTRACT_STATUS,
    intervals=INTERVAL_LABELS,
)


def get_db():
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def redirect(path: str, message: str = "", kind: str = "ok") -> RedirectResponse:
    if message:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}hinweis={quote(message)}&art={kind}"
    return RedirectResponse(path, status_code=303)


def render(request: Request, template: str, session: Session, **context) -> HTMLResponse:
    context.setdefault("today", date.today())
    context["hinweis"] = request.query_params.get("hinweis", "")
    context["hinweis_art"] = request.query_params.get("art", "ok")
    context["open_alert_count"] = len(insights.open_alerts(session))
    context["theme"] = prefs.get(session, "theme", "auto")
    return templates.TemplateResponse(request, template, context)


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

        # --------------------------------------------------------------------------- #
        # App
        # --------------------------------------------------------------------------- #


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title=APP_NAME, version=__version__, docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    # ---------------------------------------------------------------- Start #

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(get_db)):
        today = date.today()
        insights.refresh_alerts(session, today)
        costs = finance.fixed_costs(session)
        month = finance.month_summary(session, today)
        series = finance.month_series(session, today, 6)
        income = finance.average_monthly_income(session, today)
        alerts = insights.open_alerts(session)

        return render(
            request,
            "dashboard.html",
            session,
            title="Übersicht",
            costs=costs,
            month=month,
            series=series,
            max_series=max([max(m.income_cents, m.expense_cents) for m in series] + [1]),
            income=income,
            free_cents=(income - costs.monthly_cents) if income else None,
            alerts=alerts[:6],
            deadlines=finance.upcoming_deadlines(session, today, 120)[:6],
            payments=finance.upcoming_payments(session, today, 30)[:8],
            briefing=briefing_service.build(session, today),
            contract_count=session.query(Contract).filter(Contract.status == "active").count(),
            transaction_count=session.query(Transaction).count(),
        )

        # ----------------------------------------------------------- Verträge #

    @app.get("/vertraege", response_class=HTMLResponse)
    def contracts(
        request: Request,
        status: str = "active",
        kategorie: str = "",
        q: str = "",
        session: Session = Depends(get_db),
    ):
        today = date.today()
        query = session.query(Contract)
        if status and status != "alle":
            query = query.filter(Contract.status == status)
        if kategorie:
            query = query.filter(Contract.category == kategorie)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Contract.name.ilike(like),
                    Contract.provider.ilike(like),
                    Contract.notes.ilike(like),
                    Contract.customer_number.ilike(like),
                )
            )
        items = query.order_by(Contract.name).all()
        rows = [{"contract": c, "timing": c.timing(today)} for c in items]
        rows.sort(
            key=lambda r: (
                r["timing"].days_until_cancel
                if r["timing"].days_until_cancel is not None
                else 10_000
            )
        )
        return render(
            request,
            "contracts.html",
            session,
            title="Verträge & Abos",
            rows=rows,
            status=status,
            kategorie=kategorie,
            q=q,
            total_monthly=sum(
                r["contract"].monthly_cents for r in rows if r["contract"].status == "active"
            ),
        )

    @app.get("/vertraege/neu", response_class=HTMLResponse)
    def contract_new(request: Request, aus_buchung: int = 0, session: Session = Depends(get_db)):
        draft = {
            "name": "",
            "provider": "",
            "kind": "abo",
            "category": "Sonstiges",
            "amount": "",
            "interval": "monthly",
            "start_date": "",
            "minimum_term_months": 0,
            "renewal_months": 12,
            "notice_months": 1,
            "notice_days": 0,
        }
        source = None
        if aus_buchung:
            source = session.get(Transaction, aus_buchung)
            if source is not None:
                hit = knowledge.lookup(f"{source.counterparty} {source.purpose}")
                draft["name"] = (
                    hit[1] if hit and hit[1] else source.counterparty
                ) or "Neuer Vertrag"
                draft["provider"] = source.counterparty
                draft["category"] = source.category or (hit[0] if hit else "Sonstiges")
                draft["amount"] = f"{abs(source.amount_cents) / 100:.2f}".replace(".", ",")
                draft["start_date"] = source.booking_date.isoformat()
        return render(
            request,
            "contract_form.html",
            session,
            title="Neuer Vertrag",
            contract=None,
            draft=draft,
            source=source,
        )

    @app.post("/vertraege/neu")
    def contract_create(
        name: str = Form(...),
        provider: str = Form(""),
        kind: str = Form("abo"),
        category: str = Form("Sonstiges"),
        amount: str = Form("0"),
        interval: str = Form("monthly"),
        start_date: str = Form(""),
        end_date: str = Form(""),
        minimum_term_months: str = Form("0"),
        renewal_months: str = Form("0"),
        notice_months: str = Form("0"),
        notice_days: str = Form("0"),
        reminder_lead_days: str = Form(""),
        customer_number: str = Form(""),
        contact_email: str = Form(""),
        website: str = Form(""),
        notes: str = Form(""),
        session: Session = Depends(get_db),
    ):
        contract = Contract(name=name.strip() or "Unbenannter Vertrag")
        _apply_contract_form(
            contract,
            provider=provider,
            kind=kind,
            category=category,
            amount=amount,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            minimum_term_months=minimum_term_months,
            renewal_months=renewal_months,
            notice_months=notice_months,
            notice_days=notice_days,
            reminder_lead_days=reminder_lead_days,
            customer_number=customer_number,
            contact_email=contact_email,
            website=website,
            notes=notes,
        )
        session.add(contract)
        session.flush()
        matching.rematch_all(session, only_unassigned=True)
        return redirect(f"/vertraege/{contract.id}", f"{contract.name} angelegt.")

    @app.get("/vertraege/{contract_id}", response_class=HTMLResponse)
    def contract_detail(contract_id: int, request: Request, session: Session = Depends(get_db)):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        today = date.today()
        payments = (
            session.query(Transaction)
            .filter(Transaction.contract_id == contract.id)
            .order_by(Transaction.booking_date.desc())
            .limit(24)
            .all()
        )
        return render(
            request,
            "contract_detail.html",
            session,
            title=contract.name,
            contract=contract,
            timing=contract.timing(today),
            payments=payments,
            paid_total=sum(-t.amount_cents for t in payments if t.amount_cents < 0),
            steps=letters.checklist(contract, today),
        )

    @app.post("/vertraege/{contract_id}")
    def contract_update(
        contract_id: int,
        name: str = Form(...),
        provider: str = Form(""),
        kind: str = Form("abo"),
        category: str = Form("Sonstiges"),
        amount: str = Form("0"),
        interval: str = Form("monthly"),
        start_date: str = Form(""),
        end_date: str = Form(""),
        minimum_term_months: str = Form("0"),
        renewal_months: str = Form("0"),
        notice_months: str = Form("0"),
        notice_days: str = Form("0"),
        reminder_lead_days: str = Form(""),
        customer_number: str = Form(""),
        contact_email: str = Form(""),
        website: str = Form(""),
        notes: str = Form(""),
        status: str = Form("active"),
        session: Session = Depends(get_db),
    ):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        contract.name = name.strip() or contract.name
        contract.status = status if status in CONTRACT_STATUS else contract.status
        _apply_contract_form(
            contract,
            provider=provider,
            kind=kind,
            category=category,
            amount=amount,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            minimum_term_months=minimum_term_months,
            renewal_months=renewal_months,
            notice_months=notice_months,
            notice_days=notice_days,
            reminder_lead_days=reminder_lead_days,
            customer_number=customer_number,
            contact_email=contact_email,
            website=website,
            notes=notes,
        )
        return redirect(f"/vertraege/{contract.id}", "Gespeichert.")

    @app.get("/vertraege/{contract_id}/bearbeiten", response_class=HTMLResponse)
    def contract_edit(contract_id: int, request: Request, session: Session = Depends(get_db)):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        return render(
            request,
            "contract_form.html",
            session,
            title=f"{contract.name} bearbeiten",
            contract=contract,
            draft=None,
            source=None,
        )

    @app.post("/vertraege/{contract_id}/status")
    def contract_status(
        contract_id: int,
        status: str = Form(...),
        session: Session = Depends(get_db),
    ):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        if status in CONTRACT_STATUS:
            contract.status = status
            if status == "cancelled":
                contract.cancelled_on = date.today()
        return redirect(f"/vertraege/{contract.id}", f"Status: {contract.status_label}.")

    @app.post("/vertraege/{contract_id}/löschen")
    def contract_delete(contract_id: int, session: Session = Depends(get_db)):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        name = contract.name
        session.query(Transaction).filter(Transaction.contract_id == contract.id).update(
            {"contract_id": None}
        )
        session.query(Alert).filter(Alert.contract_id == contract.id).delete()
        session.delete(contract)
        return redirect("/vertraege", f"{name} gelöscht.")

    @app.get("/vertraege/{contract_id}/kuendigung", response_class=HTMLResponse)
    def contract_letter(
        contract_id: int,
        request: Request,
        zum: str = "",
        session: Session = Depends(get_db),
    ):
        contract = session.get(Contract, contract_id)
        if contract is None:
            return redirect("/vertraege", "Vertrag nicht gefunden.", "warn")
        today = date.today()
        text = letters.cancellation_letter(
            contract,
            today=today,
            sender_name=prefs.get(session, "owner_name", ""),
            effective_date=parse_date(zum),
        )
        return render(
            request,
            "letter.html",
            session,
            title=f"Kündigung: {contract.name}",
            contract=contract,
            timing=contract.timing(today),
            letter=text,
            steps=letters.checklist(contract, today),
        )

        # ------------------------------------------------------------- Finanzen #

    @app.get("/finanzen", response_class=HTMLResponse)
    def finances(
        request: Request,
        q: str = "",
        kategorie: str = "",
        art: str = "",
        monate: int = 3,
        session: Session = Depends(get_db),
    ):
        today = date.today()
        from ..dates import add_months

        since = add_months(today.replace(day=1), -(max(1, monate) - 1))
        query = session.query(Transaction).filter(Transaction.booking_date >= since)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(Transaction.counterparty.ilike(like), Transaction.purpose.ilike(like))
            )
        if kategorie:
            query = query.filter(Transaction.category == kategorie)
        if art == "ein":
            query = query.filter(Transaction.amount_cents > 0)
        elif art == "aus":
            query = query.filter(Transaction.amount_cents < 0)
        rows = (
            query.order_by(Transaction.booking_date.desc(), Transaction.id.desc()).limit(500).all()
        )

        return render(
            request,
            "finance.html",
            session,
            title="Einnahmen & Ausgaben",
            rows=rows,
            q=q,
            kategorie=kategorie,
            art=art,
            monate=monate,
            income=sum(t.amount_cents for t in rows if t.amount_cents > 0),
            expense=sum(-t.amount_cents for t in rows if t.amount_cents < 0),
            by_category=finance.spending_by_category(session, today, max(1, monate)),
            contracts=session.query(Contract).order_by(Contract.name).all(),
            month=finance.month_summary(session, today),
        )

    @app.post("/finanzen/neu")
    def finance_add(
        booking_date: str = Form(...),
        amount: str = Form(...),
        direction: str = Form("aus"),
        counterparty: str = Form(""),
        purpose: str = Form(""),
        category: str = Form(""),
        contract_id: str = Form(""),
        session: Session = Depends(get_db),
    ):
        day = parse_date(booking_date) or date.today()
        cents = abs(to_cents(amount))
        if cents == 0:
            return redirect("/finanzen", "Bitte einen Betrag eingeben.", "warn")
        if direction == "aus":
            cents = -cents
        created = ledger.add_transaction(
            session,
            booking_date=day,
            amount_cents=cents,
            counterparty=counterparty,
            purpose=purpose,
            category=category,
            contract_id=_int(contract_id) or None,
        )
        if created is None:
            return redirect("/finanzen", "Diese Buchung gibt es schon.", "warn")
        return redirect("/finanzen", "Buchung gespeichert.")

    @app.post("/finanzen/{transaction_id}/zuordnen")
    def finance_assign(
        transaction_id: int,
        contract_id: str = Form(""),
        category: str = Form(""),
        merken: str = Form(""),
        session: Session = Depends(get_db),
    ):
        transaction = session.get(Transaction, transaction_id)
        if transaction is None:
            return redirect("/finanzen", "Buchung nicht gefunden.", "warn")
        target = _int(contract_id) or None
        transaction.contract_id = target
        if category:
            transaction.category = category
        elif target:
            contract = session.get(Contract, target)
            if contract:
                transaction.category = contract.category
        if merken:
            matching.learn_rule(session, transaction, target, transaction.category)
            return redirect("/finanzen", "Zugeordnet und für kuenftige Importe gemerkt.")
        return redirect("/finanzen", "Zugeordnet.")

    @app.post("/finanzen/{transaction_id}/löschen")
    def finance_delete(transaction_id: int, session: Session = Depends(get_db)):
        transaction = session.get(Transaction, transaction_id)
        if transaction is not None:
            session.delete(transaction)
        return redirect("/finanzen", "Buchung gelöscht.")

    @app.post("/finanzen/neu-zuordnen")
    def finance_rematch(session: Session = Depends(get_db)):
        changed = matching.rematch_all(session, only_unassigned=True)
        return redirect("/finanzen", f"{changed} Buchungen neu zugeordnet.")

        # --------------------------------------------------------------- Import #

    @app.get("/import", response_class=HTMLResponse)
    def import_form(request: Request, session: Session = Depends(get_db)):
        return render(
            request,
            "import.html",
            session,
            title="Kontoumsätze importieren",
            rules=session.query(MatchRule).order_by(MatchRule.hits.desc()).limit(40).all(),
            contracts=session.query(Contract).order_by(Contract.name).all(),
        )

    @app.post("/import")
    async def import_upload(
        datei: UploadFile,
        konto: str = Form(""),
        session: Session = Depends(get_db),
    ):
        payload = await datei.read()
        if not payload:
            return redirect("/import", "Die Datei war leer.", "warn")
        result = parse_csv(payload, account=konto)
        if result.problems and not result.rows:
            return redirect("/import", " ".join(result.problems), "warn")
        report = ledger.save_import(session, result, account=konto)
        insights.refresh_alerts(session, date.today())
        return redirect("/finanzen", report.as_text())

        # ---------------------------------------------------------------- Buddy #

    @app.get("/buddy", response_class=HTMLResponse)
    def buddy(request: Request, session: Session = Depends(get_db)):
        today = date.today()
        insights.refresh_alerts(session, today)
        return render(
            request,
            "buddy.html",
            session,
            title="Dein Buddy",
            briefing=briefing_service.build(session, today),
            alerts=insights.open_alerts(session),
            dismissed=session.query(Alert).filter(Alert.dismissed.is_(True)).count(),
            recurring=[
                g for g in insights.recurring_groups(session, today) if g.is_subscription_candidate
            ],
        )

    @app.post("/buddy/prüfen")
    def buddy_refresh(session: Session = Depends(get_db)):
        found = insights.refresh_alerts(session, date.today())
        return redirect("/buddy", f"Durchgesehen - {len(found)} offene Hinweise.")

    @app.post("/buddy/{alert_id}/erledigt")
    def buddy_dismiss(alert_id: int, session: Session = Depends(get_db)):
        alert = session.get(Alert, alert_id)
        if alert is not None:
            alert.dismissed = True
        return redirect("/buddy", "Erledigt.")

    @app.post("/buddy/alle-zeigen")
    def buddy_restore(session: Session = Depends(get_db)):
        session.query(Alert).filter(Alert.dismissed.is_(True)).update({"dismissed": False})
        return redirect("/buddy", "Alle Hinweise wieder eingeblendet.")

    @app.post("/buddy/test")
    def buddy_test_notification(session: Session = Depends(get_db)):
        result = notify.send(
            session,
            f"{APP_NAME} Testnachricht",
            briefing_service.build(session, date.today()).as_text(),
        )
        return redirect("/einstellungen", result.detail, "ok" if result.ok else "warn")

        # --------------------------------------------------------- Einstellungen #

    @app.get("/einstellungen", response_class=HTMLResponse)
    def settings_page(request: Request, session: Session = Depends(get_db)):
        return render(
            request,
            "settings.html",
            session,
            title="Einstellungen",
            values=prefs.all_settings(session),
            rules=session.query(MatchRule).order_by(MatchRule.pattern).all(),
            contracts=session.query(Contract).order_by(Contract.name).all(),
            db_path=str(__import__("lifeagent.config", fromlist=["settings"]).settings.db_path),
        )

    @app.post("/einstellungen")
    async def settings_save(request: Request, session: Session = Depends(get_db)):
        form = await request.form()
        prefs.set_many(session, {key: str(value) for key, value in form.items()})
        return redirect("/einstellungen", "Einstellungen gespeichert.")

    @app.post("/einstellungen/regel/{rule_id}/löschen")
    def rule_delete(rule_id: int, session: Session = Depends(get_db)):
        rule = session.get(MatchRule, rule_id)
        if rule is not None:
            session.delete(rule)
        return redirect("/einstellungen", "Regel gelöscht.")

        # --------------------------------------------------------------- Export #

    @app.get("/export/buchungen.csv")
    def export_transactions(session: Session = Depends(get_db)):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(
            ["Datum", "Betrag", "Empfänger", "Verwendungszweck", "Kategorie", "Vertrag"]
        )
        rows = session.query(Transaction).order_by(Transaction.booking_date).all()
        for row in rows:
            writer.writerow(
                [
                    row.booking_date.isoformat(),
                    f"{row.amount_cents / 100:.2f}".replace(".", ","),
                    row.counterparty,
                    row.purpose,
                    row.category,
                    row.contract.name if row.contract else "",
                ]
            )
        return Response(
            buffer.getvalue().encode("utf-8-sig"),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="buchungen.csv"'},
        )

    @app.get("/export/daten.json")
    def export_all(session: Session = Depends(get_db)):
        data = {
            "exportiert_am": datetime.now().isoformat(timespec="seconds"),
            "vertraege": [
                {
                    "name": c.name,
                    "anbieter": c.provider,
                    "art": c.kind,
                    "kategorie": c.category,
                    "status": c.status,
                    "betrag_cent": c.amount_cents,
                    "intervall": c.interval,
                    "beginn": c.start_date.isoformat() if c.start_date else None,
                    "mindestlaufzeit_monate": c.minimum_term_months,
                    "verlaengerung_monate": c.renewal_months,
                    "kuendigungsfrist_monate": c.notice_months,
                    "kuendigungsfrist_tage": c.notice_days,
                    "kundennummer": c.customer_number,
                    "notizen": c.notes,
                }
                for c in session.query(Contract).all()
            ],
            "buchungen": [
                {
                    "datum": t.booking_date.isoformat(),
                    "betrag_cent": t.amount_cents,
                    "empfaenger": t.counterparty,
                    "zweck": t.purpose,
                    "kategorie": t.category,
                    "vertrag": t.contract.name if t.contract else None,
                }
                for t in session.query(Transaction).all()
            ],
        }
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="lifeagent-daten.json"'},
        )

    @app.get("/briefing.txt", response_class=PlainTextResponse)
    def briefing_text(session: Session = Depends(get_db)):
        return briefing_service.build(session, date.today()).as_text()

    @app.get("/gesundheit")
    def health(session: Session = Depends(get_db)):
        return {
            "status": "ok",
            "version": __version__,
            "vertraege": session.query(Contract).count(),
            "buchungen": session.query(Transaction).count(),
            "offene_hinweise": len(insights.open_alerts(session)),
        }

    return app


def _apply_contract_form(contract: Contract, **form) -> None:
    contract.provider = (form.get("provider") or "").strip()
    contract.kind = form.get("kind") if form.get("kind") in CONTRACT_KINDS else "abo"
    contract.category = (form.get("category") or "Sonstiges").strip()
    contract.amount_cents = abs(to_cents(form.get("amount")))
    interval = (form.get("interval") or "monthly").lower()
    contract.interval = interval if interval in INTERVAL_LABELS else "monthly"
    contract.start_date = parse_date(form.get("start_date"))
    contract.end_date = parse_date(form.get("end_date"))
    contract.minimum_term_months = max(0, _int(form.get("minimum_term_months")))
    contract.renewal_months = max(0, _int(form.get("renewal_months")))
    contract.notice_months = max(0, _int(form.get("notice_months")))
    contract.notice_days = max(0, _int(form.get("notice_days")))
    lead = str(form.get("reminder_lead_days") or "").strip()
    contract.reminder_lead_days = _int(lead) if lead else None
    contract.customer_number = (form.get("customer_number") or "").strip()
    contract.contact_email = (form.get("contact_email") or "").strip()
    contract.website = (form.get("website") or "").strip()
    contract.notes = form.get("notes") or ""


app = create_app()
