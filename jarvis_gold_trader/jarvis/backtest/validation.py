"""Validación: separación entrenamiento/validación, prueba fuera de muestra,
walk-forward y comparación con estrategias de referencia.

Flujo:
1. Las características se calculan una sola vez sobre la serie completa: son
   causales, así que la fila ``i`` no contiene información posterior a ``i``.
2. Se elige la configuración en el tramo de ENTRENAMIENTO (rejilla pequeña de
   parámetros) usando únicamente resultados de ese tramo.
3. La configuración elegida se evalúa UNA vez en el tramo de VALIDACIÓN
   (fuera de muestra), que no ha intervenido en la selección.
4. Se compara con: cruce EMA simple, entradas aleatorias con las mismas
   salidas y comprar-y-mantener, todos con los mismos costes.
"""

from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from ..analysis import AnalysisEngine, ConfidenceCalibrator
from ..config import AppConfig
from .engine import Backtester, BacktestResult, buy_and_hold, ema_cross_signal, make_random_signal

DEFAULT_GRID = {
    "min_confluence": [4, 5],
    "stop_loss_atr": [1.0, 1.5, 2.0],
    "rr": [1.5, 2.0, 3.0],  # take_profit_atr = stop_loss_atr * rr
}


@dataclass
class ValidationReport:
    split_index: int
    split_time: pd.Timestamp
    best_params: dict
    train: BacktestResult
    test: BacktestResult
    benchmarks: dict
    grid_results: list[dict]
    calibrator: ConfidenceCalibrator
    verdict: str
    walk_forward: list[dict] = field(default_factory=list)


def apply_params(cfg: AppConfig, params: dict) -> AppConfig:
    c = copy.deepcopy(cfg)
    if "min_confluence" in params:
        c.strategy.min_confluence = int(params["min_confluence"])
    if "min_score" in params:
        c.strategy.min_score = float(params["min_score"])
    if "stop_loss_atr" in params:
        c.risk.stop_loss_atr = float(params["stop_loss_atr"])
    if "rr" in params:
        c.risk.take_profit_atr = c.risk.stop_loss_atr * float(params["rr"])
    return c


def _objective(m: dict, min_trades: int) -> float:
    """Expectativa por operación penalizando muestras pequeñas y drawdowns grandes."""
    if m["trades"] < min_trades:
        return -math.inf
    return m["expectancy"] * math.sqrt(m["trades"]) / (1 + m["max_drawdown_pct"] / 10)


def optimize(cfg: AppConfig, candles: pd.DataFrame, start: int, end: int, grid: dict | None = None,
             progress: Optional[Callable[[str], None]] = None) -> tuple[dict, list[dict]]:
    grid = grid or DEFAULT_GRID
    keys = list(grid)
    results = []
    feats_cache: dict[int, pd.DataFrame] = {}
    combos = list(itertools.product(*(grid[k] for k in keys)))
    for idx, values in enumerate(combos, 1):
        params = dict(zip(keys, values))
        c = apply_params(cfg, params)
        key = c.strategy.min_confluence
        if key not in feats_cache:
            feats_cache[key] = AnalysisEngine(c.indicators, c.strategy, c.indicators.use_volume).compute_features(candles)
        res = Backtester(c).run(candles, start, end, features=feats_cache[key])
        obj = _objective(res.metrics, cfg.backtest.min_trades_for_stats)
        results.append({**params, **{k: res.metrics[k] for k in ("trades", "win_rate", "profit_factor",
                                                                  "expectancy", "net_profit", "max_drawdown_pct")},
                        "objective": obj})
        if progress:
            progress(f"Entrenamiento {idx}/{len(combos)}: {params} → {res.metrics['trades']} ops, "
                     f"expectativa {res.metrics['expectancy']:+.2f}")
    valid = [r for r in results if r["objective"] != -math.inf]
    best = max(valid, key=lambda r: r["objective"]) if valid else results[0]
    return {k: best[k] for k in keys}, results


def run_validation(cfg: AppConfig, candles: pd.DataFrame, grid: dict | None = None,
                   progress: Optional[Callable[[str], None]] = None, walk_forward_folds: int = 0) -> ValidationReport:
    n = len(candles)
    engine = AnalysisEngine(cfg.indicators, cfg.strategy)
    split = int(n * cfg.backtest.train_ratio)
    if split - engine.min_bars < 200 or n - split < 200:
        raise ValueError("Datos insuficientes para separar entrenamiento y validación (mín. ~200 velas por tramo)")
    if progress:
        progress(f"Datos: {n} velas · entrenamiento [0, {split}) · validación [{split}, {n})")
    best, grid_results = optimize(cfg, candles, 0, split, grid, progress)
    best_cfg = apply_params(cfg, best)
    feats = AnalysisEngine(best_cfg.indicators, best_cfg.strategy, best_cfg.indicators.use_volume).compute_features(candles)
    bt = Backtester(best_cfg, keep_decisions=False)
    train = bt.run(candles, 0, split, features=feats, label="JARVIS (entrenamiento)")
    test = bt.run(candles, split, n, features=feats, label="JARVIS (fuera de muestra)")
    if progress:
        progress(f"Mejor configuración en entrenamiento: {best}")
        progress(f"Fuera de muestra: {test.metrics['trades']} ops, PF {test.metrics['profit_factor']:.2f}, "
                 f"expectativa {test.metrics['expectancy']:+.2f}")
    # referencias
    ema_res = bt.run(candles, split, n, signal_fn=ema_cross_signal, features=feats, label="Cruce EMA 9/21",
                     use_smart_close=False)
    sig_rate = max(1e-3, test.metrics["trades"] / max(1, n - split))
    rand_res = bt.run(candles, split, n, signal_fn=make_random_signal(cfg.backtest.seed, sig_rate * 1.5),
                      features=feats, label="Aleatoria (mismas salidas)")
    bh = buy_and_hold(candles, split, n, best_cfg)
    benchmarks = {"ema_cross": ema_res, "random": rand_res, "buy_hold": bh}
    calib = ConfidenceCalibrator(min_trades=cfg.backtest.min_trades_for_stats).fit(
        [(t.score, t.net_pnl) for t in test.trades], "backtest fuera de muestra")
    verdict = make_verdict(train.metrics, test.metrics, ema_res.metrics, rand_res.metrics, cfg.backtest.min_trades_for_stats)
    wf = walk_forward(cfg, candles, walk_forward_folds, grid, progress) if walk_forward_folds > 1 else []
    return ValidationReport(split, pd.Timestamp(candles["time"].iloc[split]), best, train, test, benchmarks,
                            grid_results, calib, verdict, wf)


def make_verdict(train: dict, test: dict, ema: dict, rnd: dict, min_trades: int) -> str:
    lines = []
    if test["trades"] < min_trades:
        lines.append(f"✗ Muestra fuera de muestra insuficiente ({test['trades']} < {min_trades} operaciones): "
                     "no hay evidencia estadística.")
    pf = test["profit_factor"]
    if test["expectancy"] > 0 and pf > 1.1:
        lines.append(f"✓ Expectativa positiva fuera de muestra ({test['expectancy']:+.2f} USD/op, PF {pf:.2f}).")
    else:
        lines.append(f"✗ Sin ventaja fuera de muestra (expectativa {test['expectancy']:+.2f} USD/op, PF {pf:.2f}). "
                     "La estrategia NO debe considerarse funcional.")
    if train["expectancy"] <= 0:
        lines.append("⚠ Ni la mejor configuración tiene expectativa positiva en entrenamiento: un resultado "
                     "positivo fuera de muestra puede deberse al azar.")
    if train["expectancy"] > 0 and test["expectancy"] < train["expectancy"] * 0.5:
        lines.append("⚠ Degradación notable entre entrenamiento y validación: posible sobreajuste.")
    if test["net_profit"] > max(ema["net_profit"], rnd["net_profit"]):
        lines.append("✓ Supera a las referencias (cruce EMA y aleatoria) en el tramo de validación.")
    else:
        lines.append("✗ No supera a todas las referencias en el tramo de validación.")
    lines.append("Resultados simulados. El rendimiento pasado no garantiza resultados futuros.")
    return "\n".join(lines)


def walk_forward(cfg: AppConfig, candles: pd.DataFrame, folds: int, grid: dict | None = None,
                 progress: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Optimiza en una ventana y valida en la siguiente, avanzando en el tiempo."""
    n = len(candles)
    engine = AnalysisEngine(cfg.indicators, cfg.strategy)
    size = (n - engine.min_bars) // (folds + 1)
    out = []
    for k in range(folds):
        tr_s, tr_e = engine.min_bars + k * size, engine.min_bars + (k + 1) * size
        te_e = min(n, tr_e + size)
        best, _ = optimize(cfg, candles, tr_s, tr_e, grid)
        c = apply_params(cfg, best)
        res = Backtester(c).run(candles, tr_e, te_e)
        out.append({"fold": k + 1, "params": best, **{m: res.metrics[m] for m in
                                                       ("trades", "win_rate", "profit_factor", "expectancy",
                                                        "net_profit", "max_drawdown_pct")}})
        if progress:
            progress(f"Walk-forward {k + 1}/{folds}: {best} → expectativa {res.metrics['expectancy']:+.2f}")
    return out
