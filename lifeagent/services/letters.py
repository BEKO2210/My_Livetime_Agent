"""Fertige Textbausteine - vor allem das Kündigungsschreiben.

Der Nutzer soll nicht googeln müssen, wie man kündigt. Text kopieren,
Absender ergänzen, abschicken. Formulierung bewusst knapp und rechtssicher
üblich (fristgerechte Kündigung + Bestätigungsbitte).
"""

from __future__ import annotations

from datetime import date

from ..models import Contract


def cancellation_letter(
    contract: Contract,
    today: date | None = None,
    sender_name: str = "",
    effective_date: date | None = None,
) -> str:
    today = today or date.today()
    timing = contract.timing(today)
    target = effective_date or timing.period_end

    if target:
        when = f"zum {target:%d.%m.%Y}"
    else:
        when = "zum nächstmöglichen Termin"

    lines = [
        f"{sender_name or '[Dein Vorname Nachname]'}",
        "[Straße und Hausnummer]",
        "[PLZ Ort]",
        "",
        contract.provider or "[Anbieter]",
        "[Straße des Anbieters]",
        "[PLZ Ort]",
        "",
        f"{today:%d.%m.%Y}",
        "",
        f"Kündigung {contract.name}"
        + (f" - Kundennummer {contract.customer_number}" if contract.customer_number else ""),
        "",
        "Sehr geehrte Damen und Herren,",
        "",
        f"hiermit kündige ich den oben genannten Vertrag fristgerecht {when}.",
        "Sollte eine Kündigung zu diesem Termin nicht möglich sein, kündige ich",
        "zum nächstmöglichen Zeitpunkt.",
        "",
        "Bitte bestätigen Sie mir die Kündigung schriftlich unter Angabe des",
        "Beendigungsdatums. Eine Einzugsermächtigung widerrufe ich mit Wirkung",
        "zum Vertragsende.",
        "",
        "Mit freundlichen Grüßen",
        "",
        "",
        f"{sender_name or '[Unterschrift]'}",
    ]
    return "\n".join(lines)


def checklist(contract: Contract, today: date | None = None) -> list[str]:
    """Was der Nutzer beim Kündigen konkret tun sollte."""
    timing = contract.timing(today or date.today())
    steps = [
        "Kündigung schriftlich verschicken (E-Mail mit Lesebestätigung oder Einschreiben).",
        "Versanddatum und Beleg aufheben - im Streitfall zählt der Nachweis.",
    ]
    if contract.website:
        steps.insert(
            0, f"Prüfen, ob es beim Anbieter einen Kündigungsbutton gibt: {contract.website}"
        )
    else:
        steps.insert(
            0,
            "Online-Verträge haben seit Juli 2022 einen Kündigungsbutton - dort ist es am schnellsten.",
        )
    if timing.cancel_by:
        steps.append(f"Spätestes Zugangsdatum beim Anbieter: {timing.cancel_by:%d.%m.%Y}.")
    steps.append("Nach der Bestätigung den Vertrag hier auf 'gekündigt' setzen.")
    return steps
