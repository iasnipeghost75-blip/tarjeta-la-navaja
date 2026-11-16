"""Conexión de SOLO LECTURA con MetaTrader 5 (cuentas DEMO).

Reglas de seguridad aplicadas:
* Se usa la sesión ya iniciada en el terminal MT5: JARVIS NO pide ni guarda
  contraseñas (``mt5.initialize()`` sin credenciales).
* Si la cuenta conectada no es DEMO, se desconecta inmediatamente y se lanza
  ``SafetyViolation``.
* Este módulo solo LEE datos (ticks y velas). No existe ninguna llamada de
  envío de órdenes en todo el proyecto: la ejecución es simulada en local.

El paquete ``MetaTrader5`` solo está disponible en Windows con el terminal
instalado. En otros sistemas use la fuente ``synthetic`` o ``csv``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from ..safety import SafetyViolation
from .base import CANDLE_COLUMNS, TIMEFRAME_MINUTES, DataError, MarketDataProvider, Tick

ACCOUNT_TRADE_MODE_DEMO = 0  # valor de mt5.ACCOUNT_TRADE_MODE_DEMO


def _import_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as exc:  # pragma: no cover - depende de la plataforma
        raise DataError(
            "El paquete MetaTrader5 no está instalado o la plataforma no es Windows. "
            "Instale 'MetaTrader5' en Windows con el terminal MT5 abierto en una cuenta DEMO, "
            "o use data_source='synthetic'."
        ) from exc
    return mt5


class MT5DemoProvider(MarketDataProvider):
    name = "mt5"

    def __init__(self, symbol_variants: Sequence[str] = ("XAUUSD", "XAUUSDm"), terminal_path: str = "",
                 mt5_module: Any = None) -> None:
        super().__init__()
        self.symbol_variants = list(symbol_variants)
        self.terminal_path = terminal_path
        self._mt5 = mt5_module  # inyectable para pruebas
        self.account_info: dict = {}

    @property
    def mt5(self):
        if self._mt5 is None:
            self._mt5 = _import_mt5()
        return self._mt5

    def _tf_const(self, timeframe: str):
        mapping = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
                   "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1"}
        if timeframe not in mapping:
            raise DataError(f"Temporalidad no soportada: {timeframe}")
        return getattr(self.mt5, mapping[timeframe])

    def connect(self) -> None:
        mt5 = self.mt5
        ok = mt5.initialize(path=self.terminal_path) if self.terminal_path else mt5.initialize()
        if not ok:
            raise DataError(f"No se pudo inicializar MetaTrader 5: {mt5.last_error()}")
        info = mt5.account_info()
        if info is None:
            mt5.shutdown()
            raise DataError("MetaTrader 5 no tiene ninguna cuenta conectada")
        demo_const = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", ACCOUNT_TRADE_MODE_DEMO)
        if info.trade_mode != demo_const:
            mt5.shutdown()
            raise SafetyViolation(
                "La cuenta conectada en MetaTrader 5 NO es DEMO. JARVIS se niega a funcionar con cuentas reales."
            )
        self.account_info = {"login": info.login, "server": info.server, "currency": info.currency,
                             "balance": info.balance, "leverage": info.leverage, "trade_mode": "DEMO"}
        self.symbol = self._resolve_symbol()
        self.connected = True

    def _resolve_symbol(self) -> str:
        mt5 = self.mt5
        for name in self.symbol_variants:
            info = mt5.symbol_info(name)
            if info is not None:
                if not info.visible:
                    mt5.symbol_select(name, True)
                return name
        found = mt5.symbols_get("*XAU*") or []
        for s in found:
            if "USD" in s.name.upper():
                mt5.symbol_select(s.name, True)
                return s.name
        raise DataError(f"No se encontró ningún símbolo de oro entre {self.symbol_variants}")

    def disconnect(self) -> None:
        if self._mt5 is not None and self.connected:
            self._mt5.shutdown()
        self.connected = False

    def step(self) -> Tick:
        if not self.connected:
            raise DataError("MT5 no conectado")
        t = self.mt5.symbol_info_tick(self.symbol)
        if t is None:
            raise DataError(f"Sin tick para {self.symbol}: {self.mt5.last_error()}")
        return Tick(time=datetime.fromtimestamp(t.time, tz=timezone.utc), bid=float(t.bid),
                    ask=float(t.ask), volume=float(getattr(t, "volume", 0) or 0))

    def get_candles(self, timeframe: str, count: int, include_forming: bool = False) -> pd.DataFrame:
        if not self.connected:
            raise DataError("MT5 no conectado")
        start_pos = 0 if include_forming else 1  # posición 0 = vela en formación
        rates = self.mt5.copy_rates_from_pos(self.symbol, self._tf_const(timeframe), start_pos, int(count))
        if rates is None or len(rates) == 0:
            raise DataError(f"Sin velas {timeframe} para {self.symbol}: {self.mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        vol_col = "real_volume" if "real_volume" in df and df["real_volume"].sum() > 0 else "tick_volume"
        df["volume"] = df[vol_col].astype(float) if vol_col in df else 0.0
        self._real_volume = vol_col == "real_volume"
        return df[CANDLE_COLUMNS].reset_index(drop=True)

    def has_real_volume(self) -> bool:
        return getattr(self, "_real_volume", False)

    def describe(self) -> str:
        acc = self.account_info
        return f"MT5 DEMO {acc.get('server', '?')} · {self.symbol}"


assert set(TIMEFRAME_MINUTES) == {"M1", "M5", "M15", "M30", "H1"}
