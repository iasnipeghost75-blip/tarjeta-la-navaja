import numpy as np
import pandas as pd
import pytest

from jarvis.analysis import AnalysisEngine
from jarvis.analysis import indicators as ind
from jarvis.analysis.structure import confirmed_pivots


def test_ema_matches_recursive_definition():
    s = pd.Series(np.arange(1, 31, dtype=float))
    e = ind.ema(s, 5)
    alpha = 2 / 6
    val = s.iloc[0]
    for x in s.iloc[1:]:
        val = alpha * x + (1 - alpha) * val
    assert e.iloc[-1] == pytest.approx(val)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(100, dtype=float))
    assert ind.rsi(up, 14).iloc[-1] == pytest.approx(100)
    r = ind.rsi(pd.Series(np.random.default_rng(0).normal(0, 1, 500).cumsum() + 100), 14).dropna()
    assert r.between(0, 100).all()


def test_atr_positive(candles):
    a = ind.atr(candles, 14).dropna()
    assert (a > 0).all()


def test_macd_hist_is_line_minus_signal(candles):
    m = ind.macd(candles["close"]).dropna()
    assert np.allclose(m["macd_hist"], m["macd"] - m["macd_signal"])


def test_pivots_confirmed_with_delay():
    high = pd.Series([1, 2, 3, 10, 3, 2, 1, 1, 1, 1], dtype=float)
    df = pd.DataFrame({"high": high, "low": high - 0.5})
    piv = confirmed_pivots(df, k=3)
    assert np.isnan(piv["swing_high"].iloc[5])  # el pivote en 3 aún no está confirmado
    assert piv["swing_high"].iloc[6] == 10  # confirmado en 3 + k


def test_all_features_are_causal(candles):
    """Calcular con datos truncados debe dar exactamente lo mismo en las filas comunes."""
    eng = AnalysisEngine()
    full = eng.compute_features(candles)
    cut = 1700
    part = eng.compute_features(candles.iloc[:cut])
    for col in part.columns:
        a, b = full[col].iloc[:cut], part[col]
        if a.dtype == object or a.dtype == bool:
            assert a.equals(b), col
        else:
            assert np.allclose(a.astype(float), b.astype(float), equal_nan=True), col


def test_talib_equivalence_if_available(candles):
    talib = pytest.importorskip("talib")
    c = candles["close"].to_numpy(float)
    assert np.allclose(ind.rsi(candles["close"], 14).to_numpy()[100:], talib.RSI(c, 14)[100:], atol=1e-6)
    assert np.allclose(ind.ema(candles["close"], 21).to_numpy()[100:], talib.EMA(c, 21)[100:], rtol=1e-3)
