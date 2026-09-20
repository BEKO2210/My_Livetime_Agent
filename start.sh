#!/usr/bin/env bash
# Startet den Life Agent. Beim ersten Mal wird alles Noetige eingerichtet.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 wurde nicht gefunden."
  echo "Bitte von https://www.python.org/downloads/ installieren und danach erneut starten."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Richte die Umgebung ein (einmalig, dauert ein bis zwei Minuten)..."
  "$PYTHON_BIN" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
  echo "Fertig."
fi

exec ./.venv/bin/python -m lifeagent "$@"
