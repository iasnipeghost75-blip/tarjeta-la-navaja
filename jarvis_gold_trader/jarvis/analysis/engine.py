"""Motor de análisis "IA" de JARVIS: confluencia multi-factor + filtros de señales falsas.

Principios:
* Nunca se genera una señal por un solo indicador: se exige un mínimo de
  factores coincidentes (``min_confluence`` >= 2) y una puntuación mínima.
* Todas las características se calculan de forma causal y se evalúan sobre
  velas CERRADAS: el backtest y el simulador en vivo usan exactamente el mismo
  código, lo que evita sesgo de anticipación (look-ahead).
* La "puntuación" mide confluencia técnica, NO es una probabilidad. La
  probabilidad histórica se obtiene aparte (``confidence.py``) a partir de
  resultados de backtesting/simulación, con su intervalo de confianza.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..config import IndicatorConfig, StrategyConfig
from . import indicators as ind
from .structure import Level, breaks, confirmed_pivots, structure_trend, support_resistance_levels

FACTOR_LABELS = {
    "ema_alignment": "Alineación EMA 9/21",
    "trend_filter": "Filtro de tendencia EMA 200",
    "macd_momentum": "Momento MACD",
    "rsi_zone": "Zona RSI favorable",
    "structure": "Estructura de mercado / ruptura",
    "volume": "Confirmación de volumen",
    "volatility_ok": "Volatilidad operable",
}
FACTOR_WEIGHTS = {"ema_alignment": 20, "trend_filter": 15, "macd_momentum": 15, "rsi_zone": 15,
                  "structure": 20, "volume": 10, "volatility_ok": 5}
FILTER_LABELS = {
    "overextended": "Precio sobre-extendido respecto a EMA21",
    "extreme_volatility": "Volatilidad extrema",
    "fakeout": "Ruptura fallida reciente (posible trampa)",
    "divergence": "Divergencia RSI contra la señal",
    "choppy": "Mercado lateral/errático (cruces EMA frecuentes)",
}


@dataclass
class FactorResult:
    key: str
    label: str
    passed: bool
    weight: float
    detail: str


@dataclass
class DirectionEvaluation:
    side: str  # "BUY" | "SELL"
    score: float
    confluence: int
    factors: list[FactorResult]
    filters: list[str]
    triggered: bool

    @property
    def valid(self) -> bool:
        return self.triggered and not self.filters


@dataclass
class Signal:
    id: str
    side: str
    time: pd.Timestamp
    price: float
    score: float
    confluence: int
    atr: float
    factors: list[FactorResult]
    explanation: str
    timeframe: str = "M5"
    historical: Optional[dict] = None


@dataclass
class MarketAnalysis:
    time: pd.Timestamp
    price: float
    timeframe: str
    trend: str
    trend_strength: float
    trend_change: Optional[str]
    structure: str
    ema_fast: float
    ema_mid: float
    ema_slow: float
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    atr: float
    atr_ratio: float
    volatility_state: str
    volume_state: str
    levels: list[Level]
    long_eval: DirectionEvaluation
    short_eval: DirectionEvaluation
    signal: Optional[Signal] = None
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Tendencia {self.trend.upper()} (fuerza {self.trend_strength:.0f}/100) · estructura {self.structure}",
            f"EMA9 {self.ema_fast:.2f} · EMA21 {self.ema_mid:.2f} · EMA200 {self.ema_slow:.2f}",
            f"RSI {self.rsi:.1f} · MACD hist {self.macd_hist:+.3f} · ATR {self.atr:.2f} ({self.volatility_state})",
            f"Volumen: {self.volume_state}",
        ]
        if self.trend_change:
            lines.append(f"⚠ Cambio de tendencia: {self.trend_change}")
        lines.extend(self.notes)
        return lines


class AnalysisEngine:
    def __init__(self, ind_cfg: IndicatorConfig | None = None, strat_cfg: StrategyConfig | None = None,
                 use_volume: bool = True) -> None:
        self.ic = ind_cfg or IndicatorConfig()
        self.sc = strat_cfg or StrategyConfig()
        self.use_volume = use_volume and self.ic.use_volume

    @property
    def min_bars(self) -> int:
        return max(self.ic.ema_slow if self.ic.use_ema200_filter else self.ic.ema_mid, self.ic.macd_slow + self.ic.macd_signal) + 5

    def active_factors(self) -> list[str]:
        keys = ["ema_alignment", "volatility_ok"]
        if self.ic.use_ema200_filter:
            keys.append("trend_filter")
        if self.ic.use_macd:
            keys.append("macd_momentum")
        if self.ic.use_rsi:
            keys.append("rsi_zone")
        if self.ic.use_structure:
            keys.append("structure")
        if self.use_volume:
            keys.append("volume")
        return keys

    # ------------------------------------------------------------ características
    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        ic = self.ic
        f = df.copy().reset_index(drop=True)
        c = f["close"]
        f["ema_fast"] = ind.ema(c, ic.ema_fast)
        f["ema_mid"] = ind.ema(c, ic.ema_mid)
        f["ema_slow"] = ind.ema(c, ic.ema_slow)
        f["rsi"] = ind.rsi(c, ic.rsi_period)
        f = pd.concat([f, ind.macd(c, ic.macd_fast, ic.macd_slow, ic.macd_signal)], axis=1)
        f["atr"] = ind.atr(f, ic.atr_period)
        f["atr_median"] = f["atr"].rolling(100, min_periods=20).median()
        f["atr_ratio"] = f["atr"] / f["atr_median"]
        vol = f["volume"].astype(float) if "volume" in f else pd.Series(0.0, index=f.index)
        f["vol_sma"] = ind.sma(vol, ic.volume_period)
        f["vol_ratio"] = vol / f["vol_sma"].replace(0, np.nan)
        piv = confirmed_pivots(f, ic.swing_lookback)
        f = pd.concat([f, piv], axis=1)
        f["struct_trend"] = structure_trend(piv)
        f = pd.concat([f, breaks(f, piv)], axis=1)
        cross_up = (f["ema_fast"] > f["ema_mid"]) & (f["ema_fast"].shift(1) <= f["ema_mid"].shift(1))
        cross_dn = (f["ema_fast"] < f["ema_mid"]) & (f["ema_fast"].shift(1) >= f["ema_mid"].shift(1))
        f["ema_cross_up"], f["ema_cross_down"] = cross_up, cross_dn
        f["ema_crosses_20"] = (cross_up | cross_dn).astype(int).rolling(20, min_periods=1).sum()
        f["ema_slow_slope"] = f["ema_slow"].diff(5)
        self._score_columns(f)
        return f

    def _factor_frames(self, f: pd.DataFrame) -> tuple[dict, dict]:
        ic = self.ic
        c = f["close"]
        hist = f["macd_hist"]
        recent_bos_up = f["bos_up"].rolling(3, min_periods=1).max().astype(bool)
        recent_bos_dn = f["bos_down"].rolling(3, min_periods=1).max().astype(bool)
        vol_ok = f["atr_ratio"].between(0.6, 2.0)
        long = {
            "ema_alignment": (f["ema_fast"] > f["ema_mid"]) & (c > f["ema_mid"]),
            "trend_filter": (c > f["ema_slow"]) & (f["ema_slow_slope"] >= 0),
            "macd_momentum": (hist > 0) & (hist > hist.shift(1)),
            "rsi_zone": (f["rsi"] > 50) & (f["rsi"] < ic.rsi_overbought),
            "structure": recent_bos_up | (f["struct_trend"] == 1),
            "volume": f["vol_ratio"] > 1.0,
            "volatility_ok": vol_ok,
        }
        short = {
            "ema_alignment": (f["ema_fast"] < f["ema_mid"]) & (c < f["ema_mid"]),
            "trend_filter": (c < f["ema_slow"]) & (f["ema_slow_slope"] <= 0),
            "macd_momentum": (hist < 0) & (hist < hist.shift(1)),
            "rsi_zone": (f["rsi"] < 50) & (f["rsi"] > ic.rsi_oversold),
            "structure": recent_bos_dn | (f["struct_trend"] == -1),
            "volume": f["vol_ratio"] > 1.0,
            "volatility_ok": vol_ok,
        }
        return long, short

    def _score_columns(self, f: pd.DataFrame) -> None:
        sc = self.sc
        keys = self.active_factors()
        total_w = sum(FACTOR_WEIGHTS[k] for k in keys)
        long, short = self._factor_frames(f)
        for side, facs in (("long", long), ("short", short)):
            score = sum(facs[k].fillna(False).astype(float) * FACTOR_WEIGHTS[k] for k in keys) * 100.0 / total_w
            count = sum(facs[k].fillna(False).astype(int) for k in keys)
            f[f"{side}_score"] = score
            f[f"{side}_count"] = count
            for k in keys:
                f[f"{side}_f_{k}"] = facs[k].fillna(False).astype(bool)
        ext = (f["close"] - f["ema_mid"]).abs() > self.sc.max_extension_atr * f["atr"]
        extreme = f["atr_ratio"] > 2.5
        choppy = f["ema_crosses_20"] >= 4
        roll_max = f["close"].rolling(12, min_periods=12).max()
        roll_min = f["close"].rolling(12, min_periods=12).min()
        bear_div = (f["close"] >= roll_max) & (f["rsi"] < f["rsi"].rolling(12, min_periods=12).max() - 5)
        bull_div = (f["close"] <= roll_min) & (f["rsi"] > f["rsi"].rolling(12, min_periods=12).min() + 5)
        trap_up = f["failed_break_up"].rolling(3, min_periods=1).max().astype(bool)
        trap_dn = f["failed_break_down"].rolling(3, min_periods=1).max().astype(bool)
        f["long_filters"] = _join_flags({"overextended": ext, "extreme_volatility": extreme, "fakeout": trap_up,
                                         "divergence": bear_div, "choppy": choppy})
        f["short_filters"] = _join_flags({"overextended": ext, "extreme_volatility": extreme, "fakeout": trap_dn,
                                          "divergence": bull_div, "choppy": choppy})
        for side in ("long", "short"):
            s = f[f"{side}_score"]
            cnt = f[f"{side}_count"]
            ok = (s >= sc.min_score) & (cnt >= sc.min_confluence) & f[f"{side}_f_ema_alignment"]
            fresh = ok & ~(ok.shift(1, fill_value=False).astype(bool))
            bos = f["bos_up"] if side == "long" else f["bos_down"]
            cross = f["ema_cross_up"] if side == "long" else f["ema_cross_down"]
            f[f"{side}_trigger"] = (fresh | (ok & (bos | cross))) & f["atr"].notna() & f["ema_slow"].notna()
            f[f"{side}_signal"] = f[f"{side}_trigger"] & (f[f"{side}_filters"] == "")

    # --------------------------------------------------------------- evaluación
    def evaluate_row(self, f: pd.DataFrame, i: int, side: str) -> DirectionEvaluation:
        key = "long" if side == "BUY" else "short"
        row = f.iloc[i]
        factors = []
        for k in self.active_factors():
            factors.append(FactorResult(k, FACTOR_LABELS[k], bool(row[f"{key}_f_{k}"]), FACTOR_WEIGHTS[k],
                                        self._factor_detail(k, row, side)))
        filters = [FILTER_LABELS[x] for x in str(row[f"{key}_filters"]).split(",") if x]
        return DirectionEvaluation(side, float(row[f"{key}_score"]), int(row[f"{key}_count"]), factors, filters,
                                   bool(row[f"{key}_trigger"]))

    def _factor_detail(self, k: str, r: pd.Series, side: str) -> str:
        if k == "ema_alignment":
            return f"EMA9 {r.ema_fast:.2f} vs EMA21 {r.ema_mid:.2f}, cierre {r.close:.2f}"
        if k == "trend_filter":
            return f"Cierre {r.close:.2f} vs EMA200 {r.ema_slow:.2f} (pendiente {r.ema_slow_slope:+.2f})"
        if k == "macd_momentum":
            return f"Histograma MACD {r.macd_hist:+.3f}"
        if k == "rsi_zone":
            return f"RSI {r.rsi:.1f}"
        if k == "structure":
            st = {1: "máximos/mínimos crecientes", -1: "máximos/mínimos decrecientes", 0: "estructura mixta"}
            return f"{st.get(int(r.struct_trend), '?')}; BOS↑ {bool(r.bos_up)} BOS↓ {bool(r.bos_down)}"
        if k == "volume":
            return f"Volumen x{r.vol_ratio:.2f} sobre su media" if pd.notna(r.vol_ratio) else "Sin datos de volumen"
        if k == "volatility_ok":
            return f"ATR/mediana = {r.atr_ratio:.2f}"
        return ""

    def analyze(self, candles: pd.DataFrame, timeframe: str = "M5", features: pd.DataFrame | None = None) -> MarketAnalysis:
        """Analiza la última vela CERRADA de ``candles``."""
        if len(candles) < self.min_bars:
            raise ValueError(f"Se necesitan al menos {self.min_bars} velas cerradas (hay {len(candles)})")
        f = features if features is not None else self.compute_features(candles)
        i = len(f) - 1
        r = f.iloc[i]
        long_e, short_e = self.evaluate_row(f, i, "BUY"), self.evaluate_row(f, i, "SELL")
        trend, strength = self._trend(r)
        change = None
        if bool(r.ema_cross_up):
            change = "cruce alcista EMA9/EMA21"
        elif bool(r.ema_cross_down):
            change = "cruce bajista EMA9/EMA21"
        elif int(r.struct_trend) == 1 and bool(r.bos_down):
            change = "ruptura bajista de estructura alcista (CHoCH)"
        elif int(r.struct_trend) == -1 and bool(r.bos_up):
            change = "ruptura alcista de estructura bajista (CHoCH)"
        ratio = float(r.atr_ratio) if pd.notna(r.atr_ratio) else 1.0
        vstate = "extrema" if ratio > 2.5 else "alta" if ratio > 1.4 else "baja" if ratio < 0.7 else "normal"
        if not self.use_volume or pd.isna(r.vol_ratio):
            volume_state = "no disponible / desactivado"
        else:
            volume_state = f"{'por encima' if r.vol_ratio > 1 else 'por debajo'} de la media (x{r.vol_ratio:.2f})"
        st_lbl = {1: "alcista (HH/HL)", -1: "bajista (LH/LL)", 0: "mixta"}[int(r.struct_trend)]
        levels = support_resistance_levels(f, self.ic.swing_lookback, self.ic.sr_levels,
                                           tolerance=float(r.atr) * 0.6 if pd.notna(r.atr) else None)
        analysis = MarketAnalysis(
            time=r.time, price=float(r.close), timeframe=timeframe, trend=trend, trend_strength=strength,
            trend_change=change, structure=st_lbl, ema_fast=float(r.ema_fast), ema_mid=float(r.ema_mid),
            ema_slow=float(r.ema_slow), rsi=float(r.rsi), macd=float(r.macd), macd_signal=float(r.macd_signal),
            macd_hist=float(r.macd_hist), atr=float(r.atr), atr_ratio=ratio, volatility_state=vstate,
            volume_state=volume_state, levels=levels, long_eval=long_e, short_eval=short_e)
        for ev in (long_e, short_e):
            if ev.valid:
                analysis.signal = self._make_signal(r, ev, timeframe)
                break
        if analysis.signal is None:
            best = max((long_e, short_e), key=lambda e: e.score)
            if best.triggered and best.filters:
                analysis.notes.append(f"Señal {best.side} descartada por filtros: " + "; ".join(best.filters))
            else:
                analysis.notes.append(f"Sin señal: mejor confluencia {best.side} {best.score:.0f}/100 "
                                      f"({best.confluence} factores, mínimo {self.sc.min_confluence})")
        return analysis

    def _trend(self, r: pd.Series) -> tuple[str, float]:
        pts = 0.0
        pts += 1 if r.ema_fast > r.ema_mid else -1
        pts += 1 if r.close > r.ema_slow else -1
        pts += float(r.struct_trend)
        pts += 1 if r.macd_hist > 0 else -1
        strength = abs(pts) / 4 * 100
        if pts >= 2:
            return "alcista", strength
        if pts <= -2:
            return "bajista", strength
        return "lateral", strength

    def _make_signal(self, r: pd.Series, ev: DirectionEvaluation, timeframe: str) -> Signal:
        passed = [fr for fr in ev.factors if fr.passed]
        failed = [fr for fr in ev.factors if not fr.passed]
        side_txt = "COMPRA" if ev.side == "BUY" else "VENTA"
        text = (f"{side_txt} en {r.close:.2f}: {ev.confluence} factores coinciden (puntuación {ev.score:.0f}/100). "
                f"A favor: " + "; ".join(f"{p.label} ({p.detail})" for p in passed) + ". ")
        if failed:
            text += "En contra/neutros: " + "; ".join(p.label for p in failed) + ". "
        text += "Ningún filtro de señal falsa activo."
        ts = pd.Timestamp(r.time)
        return Signal(id=f"{ev.side}-{timeframe}-{ts.isoformat()}", side=ev.side, time=ts, price=float(r.close),
                      score=ev.score, confluence=ev.confluence, atr=float(r.atr), factors=ev.factors,
                      explanation=text, timeframe=timeframe)


def quick_trend(df: pd.DataFrame, fast: int = 9, mid: int = 21, slow: int = 200) -> str:
    """Tendencia resumida para la tabla multi-temporalidad."""
    if len(df) < mid + 2:
        return "sin datos"
    c = df["close"]
    ef, em = ind.ema(c, fast).iloc[-1], ind.ema(c, mid).iloc[-1]
    es = ind.ema(c, slow).iloc[-1] if len(df) >= slow else np.nan
    up = ef > em and (np.isnan(es) or c.iloc[-1] > es)
    dn = ef < em and (np.isnan(es) or c.iloc[-1] < es)
    return "alcista" if up else "bajista" if dn else "lateral"


def _join_flags(flags: dict[str, pd.Series]) -> pd.Series:
    parts = [s.fillna(False).astype(bool).map({True: name, False: ""}) for name, s in flags.items()]
    out = parts[0]
    for p in parts[1:]:
        out = out.str.cat(p, sep=",")
    return out.str.replace(r",+", ",", regex=True).str.strip(",")
