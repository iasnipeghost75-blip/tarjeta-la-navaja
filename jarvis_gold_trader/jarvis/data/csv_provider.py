"""Fuente de datos históricos desde CSV (reproducción vela a vela).

Formato aceptado: columnas ``time, open, high, low, close`` y opcional ``volume``
(o ``tick_volume``). Compatible con exportaciones de MetaTrader 5
(``<DATE> <TIME> <OPEN> ...`` con separador de tabulación).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import CANDLE_COLUMNS, TIMEFRAME_MINUTES, DataError, MarketDataProvider, Tick, resample_candles
from .validation import validate_candles


def load_candles_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DataError(f"No existe el archivo CSV: {p}")
    with open(p, encoding="utf-8") as fh:
        head = fh.readline()
    sep = "\t" if "\t" in head else ","
    df = pd.read_csv(p, sep=sep)
    df.columns = [c.strip("<>").strip().lower() for c in df.columns]
    if "time" not in df.columns and "date" in df.columns:
        df["time"] = df["date"]
    elif "date" in df.columns and "time" in df.columns:
        df["time"] = df["date"].astype(str) + " " + df["time"].astype(str)
    if "volume" not in df.columns:
        for alt in ("tickvol", "tick_volume", "vol", "real_volume"):
            if alt in df.columns:
                df["volume"] = df[alt]
                break
        else:
            df["volume"] = 0.0
    missing = [c for c in CANDLE_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"CSV sin columnas requeridas: {missing}")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df[CANDLE_COLUMNS].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    issues = validate_candles(df)
    if issues:
        raise DataError("CSV con datos inválidos: " + "; ".join(issues))
    return df


class CSVReplayProvider(MarketDataProvider):
    """Reproduce un histórico como si fuera tiempo real (un tick por vela base)."""

    name = "csv"

    def __init__(self, path: str | Path, warmup_bars: int = 300, spread: float = 0.30, symbol: str = "XAUUSD") -> None:
        super().__init__()
        self.path = Path(path)
        self.symbol = symbol
        self.spread = spread
        self.warmup_bars = warmup_bars
        self._df: pd.DataFrame | None = None
        self._pos = 0
        self._base_minutes = 1

    def connect(self) -> None:
        self._df = load_candles_csv(self.path)
        if len(self._df) < self.warmup_bars + 2:
            raise DataError("CSV demasiado corto para la reproducción")
        diffs = self._df["time"].diff().dropna().dt.total_seconds() / 60
        self._base_minutes = max(1, int(diffs.mode().iloc[0]))
        self._pos = self.warmup_bars
        self.connected = True

    @property
    def finished(self) -> bool:
        return self._df is not None and self._pos >= len(self._df) - 1

    def step(self) -> Tick:
        if not self.connected or self._df is None:
            raise DataError("CSV no cargado")
        if not self.finished:
            self._pos += 1
        row = self._df.iloc[self._pos - 1]
        close = float(row["close"])
        return Tick(time=row["time"].to_pydatetime(), bid=round(close - self.spread / 2, 2),
                    ask=round(close + self.spread / 2, 2), volume=float(row["volume"]))

    def get_candles(self, timeframe: str, count: int, include_forming: bool = False) -> pd.DataFrame:
        if self._df is None:
            raise DataError("CSV no cargado")
        minutes = TIMEFRAME_MINUTES[timeframe]
        if minutes < self._base_minutes:
            raise DataError(f"El CSV es de {self._base_minutes} min; no puede servir {timeframe}")
        visible = self._df.iloc[: self._pos]  # solo velas ya "ocurridas"
        if minutes == self._base_minutes:
            out = visible
        else:
            out = resample_candles(visible, timeframe)
            if not include_forming and len(out):
                last_end = visible["time"].iloc[-1] + pd.Timedelta(minutes=self._base_minutes)
                if out["time"].iloc[-1] + pd.Timedelta(minutes=minutes) > last_end:
                    out = out.iloc[:-1]
        return out.tail(count).reset_index(drop=True)

    def has_real_volume(self) -> bool:
        return self._df is not None and float(self._df["volume"].sum()) > 0
