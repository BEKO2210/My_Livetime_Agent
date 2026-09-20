"""Datenbank-Anbindung. Eine einzige SQLite-Datei unter data/lifeagent.db."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

_engine = None
_SessionFactory = None


def get_engine():
    global _engine, _SessionFactory
    if _engine is None:
        url = settings.db_url
        if url.startswith("sqlite:///") and "memory" not in url:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )

        if url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - Treiber
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _SessionFactory = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)
    return _engine


def get_session_factory():
    get_engine()
    return _SessionFactory


@contextmanager
def session_scope():
    """Session mit automatischem commit/rollback."""
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


def init_db() -> None:
    """Legt Tabellen und Standard-Einstellungen an (idempotent)."""
    from . import models  # noqa: F401  - registriert die Tabellen

    engine = get_engine()
    models.Base.metadata.create_all(engine)

    from .config import DEFAULT_SETTINGS

    with session_scope() as session:
        existing = {s.key for s in session.query(models.Setting).all()}
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing:
                session.add(models.Setting(key=key, value=value))


def reset_engine() -> None:
    """Nur für Tests: erzwingt eine neue Verbindung."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def backup_database() -> Path | None:
    """Kopiert die Datenbank in data/backups/ - täglich vom Scheduler aufgerufen."""
    source: Path = settings.db_path
    if not source.exists():
        return None
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.backup_dir / f"lifeagent-{datetime.now():%Y-%m-%d}.db"
    shutil.copy2(source, target)

    backups = sorted(settings.backup_dir.glob("lifeagent-*.db"))
    for old in backups[:-14]:  # 14 Tage aufbewahren
        old.unlink(missing_ok=True)
    return target
