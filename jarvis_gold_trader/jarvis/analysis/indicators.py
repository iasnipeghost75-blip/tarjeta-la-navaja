"""Indicadores técnicos implementados en pandas/NumPy.

Todas las funciones son CAUSALES: el valor en la fila ``i`` solo depende de las
filas ``<= i`` (sin información futura). Las fórmulas siguen las definiciones
estándar (Wilder para RSI/ATR), equivalentes a TA-Lib/pandas-ta. Si TA-Lib está
instalado se puede verificar la equivalencia con ``tests/test_indicators.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0, 100.0)
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    line = fast_ema - slow_ema
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    valid = pd.Series(np.arange(len(close)) >= slow + signal, index=close.index)
    return pd.DataFrame({"macd": line.where(valid), "macd_signal": sig.where(valid), "macd_hist": hist.where(valid)})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1)
    return tr.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def bollinger_width(close: pd.Series, period: int = 20, mult: float = 2.0) -> pd.Series:
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return (2 * mult * std) / mid
