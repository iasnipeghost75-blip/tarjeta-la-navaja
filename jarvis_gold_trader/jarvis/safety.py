"""Barreras de seguridad: el sistema nunca puede operar en modo LIVE.

- Solo existen dos modos: SIMULATION (datos sintéticos/CSV) y DEMO (datos de una
  cuenta DEMO de MetaTrader 5, con ejecución 100 % simulada en local).
- Cualquier intento de configurar un modo distinto lanza ``SafetyViolation``.
- La configuración no puede contener credenciales (contraseñas, tokens...).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


class SafetyViolation(RuntimeError):
    """Se intentó una acción prohibida (modo LIVE, credenciales, cuenta real...)."""


class TradingMode(str, Enum):
    SIMULATION = "SIMULATION"  # datos sintéticos o CSV, ejecución simulada
    DEMO = "DEMO"  # datos de cuenta DEMO MT5, ejecución simulada en local

    @classmethod
    def parse(cls, value: Any) -> "TradingMode":
        text = str(value).strip().upper()
        if text in {"LIVE", "REAL", "PRODUCTION", "PROD"}:
            raise SafetyViolation(
                "El modo LIVE/REAL está deshabilitado de forma permanente en JARVIS. "
                "Solo se permiten SIMULATION y DEMO."
            )
        try:
            return cls(text)
        except ValueError as exc:
            raise SafetyViolation(f"Modo de operación desconocido: {value!r}") from exc


# Fragmentos de claves que nunca deben aparecer en la configuración.
FORBIDDEN_KEY_FRAGMENTS = ("password", "passwd", "pwd", "secret", "token", "apikey", "api_key",
                           "pin", "iban", "card", "tarjeta", "contrasena", "contraseña")


def _walk_keys(obj: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path
            yield from _walk_keys(value, path)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _walk_keys(value, f"{prefix}[{i}]")


def assert_no_credentials(config_dict: dict) -> None:
    """Rechaza configuraciones que intenten guardar credenciales sensibles."""
    for path in _walk_keys(config_dict):
        leaf = path.rsplit(".", 1)[-1].lower()
        for frag in FORBIDDEN_KEY_FRAGMENTS:
            # "pin" debe coincidir como palabra para no bloquear p.ej. "trailing_..."
            if frag == "pin":
                if leaf == "pin" or leaf.endswith("_pin"):
                    raise SafetyViolation(f"La configuración no puede guardar credenciales: '{path}'")
            elif frag in leaf:
                raise SafetyViolation(f"La configuración no puede guardar credenciales: '{path}'")


def assert_simulated_execution() -> None:
    """Punto de control explícito: la ejecución siempre es simulada.

    Existe para documentar en el código que no hay rutas de ejecución real.
    El simulador lo invoca antes de cada apertura de posición.
    """
    return None
