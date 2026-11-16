#!/usr/bin/env python3
"""JARVIS AI GOLD TRADER — interfaz gráfica (modo SIMULACIÓN / DEMO).

Uso:
    python main.py                      # usa config/user_config.json o config/default_config.json
    python main.py --config mi.json
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS AI GOLD TRADER (solo simulación/DEMO)")
    parser.add_argument("--config", help="Ruta a un archivo de configuración JSON")
    args = parser.parse_args()
    from jarvis.ui.app import run

    return run(args.config)


if __name__ == "__main__":
    sys.exit(main())
