"""Lesen und Schreiben der Einstellungen."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import DEFAULT_SETTINGS
from ..models import Setting

SECRET_KEYS = {"smtp_password"}


def all_settings(session: Session) -> dict[str, str]:
    values = dict(DEFAULT_SETTINGS)
    for row in session.query(Setting).all():
        values[row.key] = row.value or ""
    return values


def get(session: Session, key: str, default: str = "") -> str:
    row = session.get(Setting, key)
    if row is not None and row.value not in (None, ""):
        return row.value
    return DEFAULT_SETTINGS.get(key, default)


def get_int(session: Session, key: str, default: int = 0) -> int:
    try:
        return int(str(get(session, key, str(default))).strip())
    except (TypeError, ValueError):
        return default


def set_many(session: Session, values: dict[str, str]) -> None:
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        if key in SECRET_KEYS and value == "":
            continue  # leeres Passwortfeld loescht das gespeicherte Passwort nicht
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
