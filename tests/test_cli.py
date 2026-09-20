"""Die Kommandozeile ist der Einstieg fuer den Nutzer - sie muss funktionieren."""

from __future__ import annotations

import pytest

from lifeagent.__main__ import main


@pytest.fixture(autouse=True)
def _eigene_datenbank(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEAGENT_DB_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("LIFEAGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LIFEAGENT_SCHEDULER", "0")
    from lifeagent import db

    db.reset_engine()
    yield
    db.reset_engine()


def test_beispieldaten_anlegen(capsys):
    assert main(["--beispiel"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Verträge" in ausgabe


def test_briefing_ausgeben(capsys):
    main(["--beispiel"])
    capsys.readouterr()
    assert main(["--briefing"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Feste Kosten" in ausgabe


@pytest.mark.parametrize("flag", ["--pruefen", "--prüfen"])
def test_pruefen_laeuft_in_beiden_schreibweisen(flag, capsys):
    main(["--beispiel"])
    capsys.readouterr()
    assert main([flag]) == 0
    assert "Hinweise" in capsys.readouterr().out


def test_beispieldaten_werden_nicht_doppelt_angelegt(capsys):
    main(["--beispiel"])
    capsys.readouterr()
    main(["--beispiel"])
    assert "bereits Daten" in capsys.readouterr().out
