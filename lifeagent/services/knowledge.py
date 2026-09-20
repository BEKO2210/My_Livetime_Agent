"""Kleines eingebautes Anbieter-Wissen.

Damit der Buddy schon beim ersten Import etwas erkennt, ohne dass der Nutzer
erst Regeln anlegen muss. Rein lokal, keine Abfrage im Internet.
"""

from __future__ import annotations

# Stichwort -> (Kategorie, sprechender Anbietername)
PROVIDERS: dict[str, tuple[str, str]] = {
    "netflix": ("Streaming & Medien", "Netflix"),
    "spotify": ("Streaming & Medien", "Spotify"),
    "disney": ("Streaming & Medien", "Disney+"),
    "amazon prime": ("Streaming & Medien", "Amazon Prime"),
    "prime video": ("Streaming & Medien", "Amazon Prime Video"),
    "sky deutschland": ("Streaming & Medien", "Sky"),
    "dazn": ("Streaming & Medien", "DAZN"),
    "youtube": ("Streaming & Medien", "YouTube Premium"),
    "audible": ("Streaming & Medien", "Audible"),
    "rundfunk": ("Streaming & Medien", "Rundfunkbeitrag"),
    "ard zdf": ("Streaming & Medien", "Rundfunkbeitrag"),
    "telekom": ("Mobilfunk & Internet", "Telekom"),
    "vodafone": ("Mobilfunk & Internet", "Vodafone"),
    "o2": ("Mobilfunk & Internet", "o2"),
    "1&1": ("Mobilfunk & Internet", "1&1"),
    "congstar": ("Mobilfunk & Internet", "congstar"),
    "aldi talk": ("Mobilfunk & Internet", "ALDI TALK"),
    "pyur": ("Mobilfunk & Internet", "PYUR"),
    "stadtwerke": ("Energie", "Stadtwerke"),
    "vattenfall": ("Energie", "Vattenfall"),
    "eon": ("Energie", "E.ON"),
    "e.on": ("Energie", "E.ON"),
    "rwe": ("Energie", "RWE"),
    "enbw": ("Energie", "EnBW"),
    "lichtblick": ("Energie", "LichtBlick"),
    "allianz": ("Versicherung", "Allianz"),
    "huk": ("Versicherung", "HUK-COBURG"),
    "axa": ("Versicherung", "AXA"),
    "ergo": ("Versicherung", "ERGO"),
    "debeka": ("Versicherung", "Debeka"),
    "generali": ("Versicherung", "Generali"),
    "devk": ("Versicherung", "DEVK"),
    "cosmosdirekt": ("Versicherung", "CosmosDirekt"),
    "techniker krankenkasse": ("Gesundheit", "Techniker Krankenkasse"),
    "aok": ("Gesundheit", "AOK"),
    "barmer": ("Gesundheit", "BARMER"),
    "fitness": ("Sport & Fitness", ""),
    "mcfit": ("Sport & Fitness", "McFIT"),
    "fitx": ("Sport & Fitness", "FitX"),
    "clever fit": ("Sport & Fitness", "clever fit"),
    "urban sports": ("Sport & Fitness", "Urban Sports Club"),
    "deutsche bahn": ("Mobilität", "Deutsche Bahn"),
    "db vertrieb": ("Mobilität", "Deutsche Bahn"),
    "deutschlandticket": ("Mobilität", "Deutschlandticket"),
    "bvg": ("Mobilität", "BVG"),
    "hvv": ("Mobilität", "HVV"),
    "shell": ("Mobilität", "Shell"),
    "aral": ("Mobilität", "Aral"),
    "adac": ("Mobilität", "ADAC"),
    "microsoft": ("Software & Cloud", "Microsoft"),
    "adobe": ("Software & Cloud", "Adobe"),
    "google": ("Software & Cloud", "Google"),
    "apple.com/bill": ("Software & Cloud", "Apple"),
    "itunes": ("Software & Cloud", "Apple"),
    "dropbox": ("Software & Cloud", "Dropbox"),
    "openai": ("Software & Cloud", "OpenAI"),
    "anthropic": ("Software & Cloud", "Anthropic"),
    "github": ("Software & Cloud", "GitHub"),
    "hetzner": ("Software & Cloud", "Hetzner"),
    "ionos": ("Software & Cloud", "IONOS"),
    "strato": ("Software & Cloud", "STRATO"),
    "rewe": ("Lebensmittel", "REWE"),
    "edeka": ("Lebensmittel", "EDEKA"),
    "lidl": ("Lebensmittel", "Lidl"),
    "aldi": ("Lebensmittel", "ALDI"),
    "penny": ("Lebensmittel", "PENNY"),
    "kaufland": ("Lebensmittel", "Kaufland"),
    "netto": ("Lebensmittel", "netto"),
    "dm-drogerie": ("Einkauf", "dm"),
    "rossmann": ("Einkauf", "Rossmann"),
    "amazon": ("Einkauf", "Amazon"),
    "ikea": ("Einkauf", "IKEA"),
    "miete": ("Wohnen", ""),
    "hausverwaltung": ("Wohnen", ""),
    "kaution": ("Wohnen", ""),
    "gehalt": ("Gehalt", ""),
    "lohn": ("Gehalt", ""),
    "bezuege": ("Gehalt", ""),
    "kindergeld": ("Familie & Kinder", "Familienkasse"),
    "familienkasse": ("Familie & Kinder", "Familienkasse"),
    "kita": ("Familie & Kinder", ""),
    "sparkasse": ("Finanzen", "Sparkasse"),
    "dkb": ("Finanzen", "DKB"),
    "paypal": ("Finanzen", "PayPal"),
    "finanzamt": ("Finanzen", "Finanzamt"),
}


def _normalize(text: str) -> str:
    """Kleinschreibung und Umlaute auf die ASCII-Form der Stichwoerter bringen."""
    return (
        (text or "")
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def lookup(text: str) -> tuple[str, str] | None:
    """Findet Kategorie und Anbietername zu einem Buchungstext."""
    haystack = _normalize(text)
    if not haystack:
        return None
    best: tuple[str, str] | None = None
    best_length = 0
    for keyword, value in PROVIDERS.items():
        if keyword in haystack and len(keyword) > best_length:
            best = value
            best_length = len(keyword)
    return best


def suggest_category(counterparty: str, purpose: str, amount_cents: int = 0) -> str:
    hit = lookup(f"{counterparty} {purpose}")
    if hit:
        return hit[0]
    return "Gehalt" if amount_cents > 0 else ""
