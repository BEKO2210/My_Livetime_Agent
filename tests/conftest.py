from __future__ import annotations

import os
from datetime import date

import pytest


@pytest.fixture()
def session(tmp_path, monkeypatch):
    """Frische Datenbank je Test."""
    monkeypatch.setenv("LIFEAGENT_DB_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LIFEAGENT_DATA_DIR", str(tmp_path))

    from lifeagent import db

    db.reset_engine()
    db.init_db()
    factory = db.get_session_factory()
    sess = factory()
    try:
        yield sess
        sess.commit()
    finally:
        sess.close()
        db.reset_engine()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEAGENT_DB_URL", f"sqlite:///{tmp_path / 'web.db'}")
    monkeypatch.setenv("LIFEAGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LIFEAGENT_SCHEDULER", "0")

    from fastapi.testclient import TestClient

    from lifeagent import db

    db.reset_engine()
    from lifeagent.web.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    db.reset_engine()


@pytest.fixture()
def heute() -> date:
    return date(2026, 6, 15)
