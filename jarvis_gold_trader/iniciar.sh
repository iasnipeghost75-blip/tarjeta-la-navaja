#!/usr/bin/env bash
# JARVIS AI GOLD TRADER - lanzador para Linux/macOS (solo simulación/DEMO)
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
python -m pytest -q
exec python main.py "$@"
