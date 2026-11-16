"""Métricas de rendimiento calculadas sobre operaciones simuladas reales del sistema."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from ..analysis.confidence import wilson_interval


def max_drawdown(equity: Iterable[float]) -> tuple[float, float]:
    eq = np.asarray(list(equity), dtype=float)
    if eq.size == 0:
        return 0.0, 0.0
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    with np.errstate(divide="ignore", invalid="ignore"):
        dd_pct = np.where(peak > 0, dd / peak * 100, 0.0)
    return float(dd.max()), float(dd_pct.max())


def compute_metrics(trades: list, equity: pd.DataFrame | None, initial_balance: float) -> dict:
    pnls = np.array([t.net_pnl for t in trades], dtype=float)
    n = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)
    win_rate = len(wins) / n if n else 0.0
    ci = wilson_interval(len(wins), n)
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    eq_series = equity["equity"] if equity is not None and len(equity) else pd.Series([initial_balance])
    mdd, mdd_pct = max_drawdown([initial_balance, *eq_series.tolist()])
    net = float(pnls.sum())
    # rachas
    max_cl = cur = 0
    for p in pnls:
        cur = cur + 1 if p <= 0 else 0
        max_cl = max(max_cl, cur)
    durations = [t.duration_seconds for t in trades]
    std = float(pnls.std(ddof=1)) if n > 1 else 0.0
    sqn = (pnls.mean() / std * math.sqrt(n)) if n > 1 and std > 0 else 0.0
    return {
        "trades": n,
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": win_rate,
        "win_rate_ci_low": ci[0],
        "win_rate_ci_high": ci[1],
        "net_profit": net,
        "return_pct": net / initial_balance * 100 if initial_balance else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": pf,
        "expectancy": float(pnls.mean()) if n else 0.0,  # esperanza matemática por operación (USD)
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": (avg_win / abs(avg_loss)) if avg_loss else 0.0,
        "max_drawdown": mdd,
        "max_drawdown_pct": mdd_pct,
        "max_consecutive_losses": int(max_cl),
        "avg_duration_min": (float(np.mean(durations)) / 60) if durations else 0.0,
        "sqn": float(sqn),
        "commissions": float(sum(t.commission for t in trades)),
    }


def format_metrics(m: dict) -> list[tuple[str, str]]:
    pf = m.get("profit_factor", 0)
    pf_txt = "∞" if pf == math.inf else f"{pf:.2f}"
    return [
        ("Operaciones", f"{m.get('trades', 0)}"),
        ("Tasa de acierto", f"{m.get('win_rate', 0):.1%} (IC95 {m.get('win_rate_ci_low', 0):.1%}–{m.get('win_rate_ci_high', 0):.1%})"),
        ("Beneficio neto", f"{m.get('net_profit', 0):+,.2f} USD ({m.get('return_pct', 0):+.2f}%)"),
        ("Profit factor", pf_txt),
        ("Expectativa / operación", f"{m.get('expectancy', 0):+.2f} USD"),
        ("Ganancia media / Pérdida media", f"{m.get('avg_win', 0):+.2f} / {m.get('avg_loss', 0):+.2f}"),
        ("Drawdown máximo", f"{m.get('max_drawdown', 0):,.2f} USD ({m.get('max_drawdown_pct', 0):.2f}%)"),
        ("Máx. pérdidas consecutivas", f"{m.get('max_consecutive_losses', 0)}"),
        ("Duración media", f"{m.get('avg_duration_min', 0):.0f} min"),
        ("SQN", f"{m.get('sqn', 0):.2f}"),
        ("Comisiones pagadas", f"{m.get('commissions', 0):,.2f} USD"),
    ]
