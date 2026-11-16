"""Backtester vela a vela que reutiliza el MISMO motor de análisis, riesgo,
simulador y cierre inteligente que la simulación en vivo.

Reglas para evitar información futura:
* La señal se calcula con la vela ``i`` CERRADA y se ejecuta en la APERTURA de
  ``i + 1``.
* SL/TP se evalúan dentro de la vela con máximo/mínimo; si en la misma vela se
  tocan ambos, se asume el peor caso (Stop Loss primero).
* Si el precio abre más allá del SL (gap), se ejecuta al precio de apertura.
* Las velas se consideran precios Bid; el Ask = Bid + spread.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..analysis import AnalysisEngine
from ..config import AppConfig
from ..trading import CostModel, MultiPositionSimulator, RiskManager, SmartCloseManager
from ..trading.models import ClosedTrade, Decision
from .metrics import compute_metrics

SignalFn = Callable[[pd.DataFrame, int], Optional[str]]


@dataclass
class BacktestResult:
    trades: list[ClosedTrade]
    equity: pd.DataFrame  # time, equity, balance
    metrics: dict
    decisions: list[Decision] = field(default_factory=list)
    label: str = "JARVIS"
    params: dict = field(default_factory=dict)

    def trades_frame(self) -> pd.DataFrame:
        return pd.DataFrame([t.to_dict() for t in self.trades])


class Backtester:
    def __init__(self, config: AppConfig, keep_decisions: bool = False) -> None:
        self.cfg = copy.deepcopy(config)
        self.keep_decisions = keep_decisions

    def run(self, candles: pd.DataFrame, start: int | None = None, end: int | None = None,
            signal_fn: SignalFn | None = None, label: str = "JARVIS", features: pd.DataFrame | None = None,
            use_smart_close: bool = True) -> BacktestResult:
        cfg = self.cfg
        engine = AnalysisEngine(cfg.indicators, cfg.strategy, use_volume=cfg.indicators.use_volume)
        f = features if features is not None else engine.compute_features(candles)
        n = len(f)
        start = max(engine.min_bars, start or 0)
        end = n if end is None else min(end, n)
        costs = CostModel.from_config(cfg.costs)
        decisions: list[Decision] = []
        sim = MultiPositionSimulator(cfg.risk.initial_balance, costs, cfg.risk,
                                     on_decision=decisions.append if self.keep_decisions else None)
        risk = RiskManager(cfg.risk, cfg.strategy, cfg.costs.contract_size)
        smart = SmartCloseManager(cfg.smart_close)
        spread = cfg.costs.spread_usd
        first_time = pd.Timestamp(f["time"].iloc[start]).to_pydatetime()
        risk.start(sim.equity, first_time)

        o, h, lo, c = (f[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        atr = f["atr"].to_numpy(float)
        atr_ratio = f["atr_ratio"].to_numpy(float)
        times = [pd.Timestamp(t).to_pydatetime() for t in f["time"]]
        long_sig = f["long_signal"].to_numpy(bool)
        short_sig = f["short_signal"].to_numpy(bool)
        scores = (f["long_score"].to_numpy(float), f["short_score"].to_numpy(float))
        pending: Optional[tuple] = None
        eq_rows = []

        for j in range(start, end):
            t = times[j]
            # 1) ejecución de la orden pendiente en la apertura
            if pending is not None:
                side, vol, sl_d, tp_d, sig_id, score, a = pending
                pending = None
                bid, ask = o[j], o[j] + spread
                entry = costs.entry_price(side, bid, ask)
                d = 1 if side == "BUY" else -1
                sim.last_bid, sim.last_ask, sim.last_time = bid, ask, t
                sim.open_position(side, vol, entry - d * sl_d, entry + d * tp_d, bid, ask, t, sig_id, score, a,
                                  entry_override=entry)
            # 2) SL/TP intrabarra (peor caso)
            for p in list(sim.positions.values()):
                if p.side == "BUY":
                    gap_sl = o[j] <= p.sl
                    hit_sl = lo[j] <= p.sl
                    hit_tp = p.tp > 0 and h[j] >= p.tp
                    if gap_sl or hit_sl:
                        px = (o[j] if gap_sl else p.sl) - costs.slippage
                        sim.close_position(p.id, 0, 0, t, "TRAILING STOP" if p.trailing_active else "STOP LOSS", px)
                    elif hit_tp:
                        sim.close_position(p.id, 0, 0, t, "TAKE PROFIT", p.tp)
                else:
                    oa, ha, la = o[j] + spread, h[j] + spread, lo[j] + spread
                    gap_sl = oa >= p.sl
                    hit_sl = ha >= p.sl
                    hit_tp = p.tp > 0 and la <= p.tp
                    if gap_sl or hit_sl:
                        px = (oa if gap_sl else p.sl) + costs.slippage
                        sim.close_position(p.id, 0, 0, t, "TRAILING STOP" if p.trailing_active else "STOP LOSS", px)
                    elif hit_tp:
                        sim.close_position(p.id, 0, 0, t, "TAKE PROFIT", p.tp)
            # 3) cierre de vela: valoración, trailing, riesgo y cierre inteligente
            bid_c, ask_c = c[j], c[j] + spread
            sim.last_bid, sim.last_ask, sim.last_time = bid_c, ask_c, t
            for p in sim.positions.values():
                sim._mark(p, bid_c, ask_c)
                sim.update_trailing(p, atr[j] if np.isfinite(atr[j]) else None)
            sim.on_bar_closed()
            events = risk.update(sim.equity, t)
            if (risk.state.daily_limit_hit or risk.state.drawdown_limit_hit) and sim.positions and events:
                sim.close_all(t, "LÍMITE DE RIESGO")
            risk.set_volatility(atr_ratio[j] if np.isfinite(atr_ratio[j]) else None)

            side = signal_fn(f, j) if signal_fn else ("BUY" if long_sig[j] else "SELL" if short_sig[j] else None)
            if use_smart_close:
                smart.evaluate(sim, t, opposite_signal_side=side)
            if side and j + 1 < end and np.isfinite(atr[j]):
                sig_id = f"{side}-{t.isoformat()}"
                chk = risk.check_entry(side, sim, sig_id, c[j], atr[j], spread, bar_index=j)
                if chk.allowed:
                    sl_d, tp_d = risk.stop_distances(atr[j])
                    score = scores[0][j] if side == "BUY" else scores[1][j]
                    pending = (side, chk.volume, sl_d, tp_d, sig_id, float(score), float(atr[j]))
                    risk.register_entry(side, sig_id, j)
            eq_rows.append((t, sim.equity, sim.balance))

        if sim.positions and end > start:
            sim.close_all(times[end - 1], "FIN DEL BACKTEST")
            eq_rows.append((times[end - 1], sim.equity, sim.balance))
        equity = pd.DataFrame(eq_rows, columns=["time", "equity", "balance"])
        metrics = compute_metrics(sim.closed, equity, cfg.risk.initial_balance)
        params = {"min_confluence": cfg.strategy.min_confluence, "min_score": cfg.strategy.min_score,
                  "stop_loss_atr": cfg.risk.stop_loss_atr, "take_profit_atr": cfg.risk.take_profit_atr}
        return BacktestResult(sim.closed, equity, metrics, decisions, label, params)


# ------------------------------------------------------------- referencias
def ema_cross_signal(f: pd.DataFrame, i: int) -> Optional[str]:
    """Estrategia de referencia: cruce simple EMA9/EMA21 (un solo indicador)."""
    if bool(f["ema_cross_up"].iat[i]):
        return "BUY"
    if bool(f["ema_cross_down"].iat[i]):
        return "SELL"
    return None


def make_random_signal(seed: int, prob: float) -> SignalFn:
    """Referencia aleatoria con la misma frecuencia de señales y las mismas salidas."""
    rng = np.random.default_rng(seed)
    cache: dict[int, Optional[str]] = {}

    def fn(f: pd.DataFrame, i: int) -> Optional[str]:
        if i not in cache:
            r = rng.random()
            cache[i] = ("BUY" if rng.random() < 0.5 else "SELL") if r < prob else None
        return cache[i]
    return fn


def buy_and_hold(candles: pd.DataFrame, start: int, end: int, cfg: AppConfig) -> dict:
    """Comprar y mantener con el lote máximo por operación y costes incluidos."""
    costs = CostModel.from_config(cfg.costs)
    seg = candles.iloc[start:end]
    vol = cfg.risk.max_lot_per_trade
    entry = costs.entry_price("BUY", seg["open"].iloc[0], seg["open"].iloc[0] + costs.spread)
    eq = cfg.risk.initial_balance + costs.pnl("BUY", entry, seg["close"].to_numpy(), vol) - costs.commission(vol)
    equity = pd.DataFrame({"time": seg["time"].to_numpy(), "equity": eq, "balance": eq})
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    final = float(eq[-1]) - costs.slippage * vol * costs.contract_size
    return {"net_profit": final - cfg.risk.initial_balance,
            "return_pct": (final / cfg.risk.initial_balance - 1) * 100,
            "max_drawdown": float(dd.max()), "max_drawdown_pct": float((dd / peak).max() * 100),
            "trades": 1, "equity": equity}
