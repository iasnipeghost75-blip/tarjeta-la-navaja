"""Estructura de mercado: pivotes (swing), soportes/resistencias y rupturas.

Un pivote en la vela ``j`` necesita ``k`` velas posteriores para confirmarse,
así que solo se considera conocido a partir de la vela ``j + k``. Todas las
series devueltas respetan esa demora (sin información futura).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def confirmed_pivots(df: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Devuelve columnas causales con el último y penúltimo swing confirmado."""
    high, low = df["high"], df["low"]
    win = 2 * k + 1
    # pivote centrado en j (usa j+k) -> se desplaza k velas para que sea conocido en j+k
    is_ph = high.rolling(win, center=True, min_periods=win).max().eq(high)
    is_pl = low.rolling(win, center=True, min_periods=win).min().eq(low)
    ph_conf = is_ph.shift(k, fill_value=False).astype(bool)
    pl_conf = is_pl.shift(k, fill_value=False).astype(bool)
    ph_val = high.shift(k).where(ph_conf)
    pl_val = low.shift(k).where(pl_conf)
    out = pd.DataFrame(index=df.index)
    out["swing_high"] = ph_val.ffill()
    out["swing_low"] = pl_val.ffill()
    # penúltimo pivote: valor anterior distinto en la serie de pivotes
    out["prev_swing_high"] = ph_val.dropna().shift(1).reindex(df.index).ffill()
    out["prev_swing_low"] = pl_val.dropna().shift(1).reindex(df.index).ffill()
    out["new_swing_high"] = ph_conf
    out["new_swing_low"] = pl_conf
    return out


def structure_trend(piv: pd.DataFrame) -> pd.Series:
    """+1 máximos y mínimos crecientes, -1 decrecientes, 0 mixto/indefinido."""
    hh = piv["swing_high"] > piv["prev_swing_high"]
    hl = piv["swing_low"] > piv["prev_swing_low"]
    lh = piv["swing_high"] < piv["prev_swing_high"]
    ll = piv["swing_low"] < piv["prev_swing_low"]
    return pd.Series(np.select([hh & hl, lh & ll], [1, -1], 0), index=piv.index)


def breaks(df: pd.DataFrame, piv: pd.DataFrame) -> pd.DataFrame:
    """Rupturas de estructura (BOS) y rupturas fallidas (falsas rupturas) por vela."""
    close, high, low = df["close"], df["high"], df["low"]
    ref_h = piv["swing_high"].shift(1)
    ref_l = piv["swing_low"].shift(1)
    out = pd.DataFrame(index=df.index)
    out["bos_up"] = (close > ref_h) & (close.shift(1) <= ref_h)
    out["bos_down"] = (close < ref_l) & (close.shift(1) >= ref_l)
    # mecha por encima del máximo pero cierre por debajo: trampa alcista
    out["failed_break_up"] = (high > ref_h) & (close < ref_h)
    out["failed_break_down"] = (low < ref_l) & (close > ref_l)
    return out


@dataclass
class Level:
    price: float
    kind: str  # "soporte" | "resistencia"
    touches: int


def support_resistance_levels(df: pd.DataFrame, k: int = 3, max_levels: int = 4, tolerance: float | None = None,
                              lookback: int = 300) -> list[Level]:
    """Agrupa pivotes confirmados recientes en niveles de soporte/resistencia."""
    if len(df) < 2 * k + 2:
        return []
    data = df.tail(lookback).reset_index(drop=True)
    last = float(data["close"].iloc[-1])
    if tolerance is None:
        rng = (data["high"] - data["low"]).tail(50).mean()
        tolerance = float(rng) if np.isfinite(rng) and rng > 0 else last * 0.001
    win = 2 * k + 1
    hi, lo = data["high"], data["low"]
    is_ph = hi.rolling(win, center=True, min_periods=win).max().eq(hi)
    is_pl = lo.rolling(win, center=True, min_periods=win).min().eq(lo)
    # solo pivotes confirmados (con k velas a la derecha dentro de los datos)
    confirmed = np.arange(len(data)) <= len(data) - 1 - k
    pts = list(hi[is_ph & confirmed]) + list(lo[is_pl & confirmed])
    if not pts:
        return []
    pts.sort()
    clusters: list[list[float]] = [[pts[0]]]
    for p in pts[1:]:
        if p - np.mean(clusters[-1]) <= tolerance:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = [Level(float(np.mean(c)), "soporte" if np.mean(c) < last else "resistencia", len(c)) for c in clusters]
    supports = sorted([lv for lv in levels if lv.kind == "soporte"], key=lambda lv: last - lv.price)[:max_levels // 2 or 1]
    resist = sorted([lv for lv in levels if lv.kind == "resistencia"], key=lambda lv: lv.price - last)[:max_levels // 2 or 1]
    return sorted(supports + resist, key=lambda lv: lv.price)
