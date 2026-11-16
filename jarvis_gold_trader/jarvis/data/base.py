"""Contratos comunes de las fuentes de datos de mercado."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

TIMEFRAME_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}
CANDLE_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


class DataError(RuntimeError):
    """Error de datos de mercado (conexión, datos corruptos, símbolo inexistente...)."""


@dataclass(frozen=True)
class Tick:
    time: datetime
    bid: float
    ask: float
    volume: float = 0.0

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class MarketDataProvider(ABC):
    """Interfaz de una fuente de datos. Ninguna implementación puede enviar órdenes."""

    name: str = "base"
    is_synthetic: bool = False

    def __init__(self) -> None:
        self.symbol: str = "XAUUSD"
        self.connected: bool = False

    @abstractmethod
    def connect(self) -> None: ...

    def disconnect(self) -> None:
        self.connected = False

    @abstractmethod
    def step(self) -> Tick:
        """Avanza (o consulta) el mercado y devuelve el último tick disponible."""

    @abstractmethod
    def get_candles(self, timeframe: str, count: int, include_forming: bool = False) -> pd.DataFrame:
        """Velas OHLCV ordenadas por tiempo. Por defecto solo velas CERRADAS (sin información futura)."""

    def has_real_volume(self) -> bool:
        return False

    def describe(self) -> str:
        return f"{self.name}:{self.symbol}"


def empty_candles() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDLE_COLUMNS)


def resample_candles(m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Agrega velas M1 a una temporalidad superior (etiqueta = apertura de la vela)."""
    minutes = TIMEFRAME_MINUTES[timeframe]
    if minutes == 1 or m1.empty:
        return m1.reset_index(drop=True)
    df = m1.set_index("time")
    agg = df.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    agg = agg.dropna(subset=["open"]).reset_index()
    return agg[CANDLE_COLUMNS]
