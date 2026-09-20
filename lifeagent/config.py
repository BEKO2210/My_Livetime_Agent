"""Konfiguration. Alles hat sinnvolle Standardwerte - nichts muss gesetzt werden."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = _env_path("LIFEAGENT_DATA_DIR", DEFAULT_DATA_DIR)
    host: str = os.environ.get("LIFEAGENT_HOST", "127.0.0.1")
    port: int = int(os.environ.get("LIFEAGENT_PORT", "8777"))
    # Der Scheduler laeuft nur, wenn die App als Dauerlaeufer gestartet wird.
    enable_scheduler: bool = os.environ.get("LIFEAGENT_SCHEDULER", "1") != "0"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "lifeagent.db"

    @property
    def db_url(self) -> str:
        override = os.environ.get("LIFEAGENT_DB_URL")
        return override or f"sqlite:///{self.db_path}"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"


settings = Settings()


# Standardwerte, die in der Datenbank als Einstellungen liegen (UI-aenderbar).
DEFAULT_SETTINGS: dict[str, str] = {
    "currency": "EUR",
    "owner_name": "",
    "reminder_lead_days": "45",  # so viele Tage vorher warnt der Buddy
    "briefing_hour": "8",  # Uhrzeit der Tagesuebersicht
    "notify_channel": "app",  # app | ntfy | email
    "ntfy_topic": "",
    "ntfy_server": "https://ntfy.sh",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_to": "",
    "monthly_income_hint": "0",  # optional, falls keine Einnahmen erfasst sind
    "theme": "auto",
}
