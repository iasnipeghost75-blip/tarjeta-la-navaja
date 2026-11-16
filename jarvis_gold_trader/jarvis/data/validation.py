"""Comprobaciones de integridad de datos. Un fallo provoca la pausa automática del sistema."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base import Tick


def validate_candles(df: pd.DataFrame, min_rows: int = 1) -> list[str]:
    issues: list[str] = []
    if df is None or len(df) < min_rows:
        return [f"Velas insuficientes ({0 if df is None else len(df)} < {min_rows})"]
    prices = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all():
        issues.append("Velas con valores NaN/infinito")
    if (prices <= 0).any():
        issues.append("Velas con precios <= 0")
    if (df["high"] < df["low"]).any():
        issues.append("Velas con máximo < mínimo")
    body_hi = df[["open", "close"]].max(axis=1)
    body_lo = df[["open", "close"]].min(axis=1)
    if ((df["high"] + 1e-9) < body_hi).any() or ((df["low"] - 1e-9) > body_lo).any():
        issues.append("Velas con OHLC incoherente")
    t = pd.to_datetime(df["time"])
    if not t.is_monotonic_increasing:
        issues.append("Marcas de tiempo desordenadas")
    if t.duplicated().any():
        issues.append("Marcas de tiempo duplicadas")
    return issues


def validate_tick(tick: Optional[Tick], prev: Optional[Tick], max_spread: float, max_jump: float) -> list[str]:
    if tick is None:
        return ["No se recibió tick"]
    issues: list[str] = []
    if not (np.isfinite(tick.bid) and np.isfinite(tick.ask)):
        issues.append("Tick con precio no numérico")
        return issues
    if tick.bid <= 0 or tick.ask <= 0:
        issues.append("Tick con precio <= 0")
    if tick.ask < tick.bid:
        issues.append("Tick con Ask < Bid")
    if tick.spread > max_spread:
        issues.append(f"Spread anómalo ({tick.spread:.2f} > {max_spread:.2f})")
    if prev is not None:
        if tick.time < prev.time:
            issues.append("Tick con tiempo anterior al previo")
        if abs(tick.mid - prev.mid) > max_jump:
            issues.append(f"Salto de precio anómalo ({abs(tick.mid - prev.mid):.2f} USD)")
    return issues
