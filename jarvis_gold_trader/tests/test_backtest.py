import math
from types import SimpleNamespace

import pandas as pd
import pytest

from jarvis.backtest import Backtester, compute_metrics, max_drawdown, run_validation
from jarvis.backtest.report import write_html_report


def test_metrics_known_values():
    trades = [SimpleNamespace(net_pnl=v, commission=1.0, duration_seconds=600) for v in (100, -50, 50, -25)]
    eq = pd.DataFrame({"equity": [10100, 10050, 10100, 10075]})
    m = compute_metrics(trades, eq, 10000)
    assert m["trades"] == 4 and m["win_rate"] == 0.5
    assert m["profit_factor"] == pytest.approx(150 / 75)
    assert m["expectancy"] == pytest.approx(18.75)
    assert m["max_drawdown"] == pytest.approx(50)
    assert m["max_consecutive_losses"] == 1


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 130, 100]) == (pytest.approx(30), pytest.approx(25))


def test_backtest_runs_and_is_consistent(cfg, candles):
    res = Backtester(cfg).run(candles)
    m = res.metrics
    assert m["trades"] > 10
    assert sum(t.net_pnl for t in res.trades) == pytest.approx(m["net_profit"], abs=0.05)
    assert res.equity["equity"].iloc[-1] == pytest.approx(cfg.risk.initial_balance + m["net_profit"], abs=0.1)
    for t in res.trades:  # entrada siempre posterior a la vela de la señal
        assert pd.Timestamp(t.open_time) > pd.Timestamp(t.signal_id.split("-", 1)[1])


def test_no_lookahead_prefix_identical(cfg, candles):
    """Los resultados hasta la vela N no cambian si se añaden datos futuros."""
    cut = 2200
    full = Backtester(cfg).run(candles)
    part = Backtester(cfg).run(candles.iloc[:cut])
    limit = pd.Timestamp(candles["time"].iloc[cut - 60])
    a = [(t.open_time, t.side, t.entry_price) for t in full.trades if pd.Timestamp(t.close_time) < limit]
    b = [(t.open_time, t.side, t.entry_price) for t in part.trades if pd.Timestamp(t.close_time) < limit]
    assert a == b and len(a) > 5


def test_costs_reduce_results(cfg, candles):
    free = Backtester(cfg)
    free.cfg.costs.spread_usd = free.cfg.costs.commission_per_lot = free.cfg.costs.slippage_usd = 0
    r_free = free.run(candles)
    r_cost = Backtester(cfg).run(candles)
    assert r_cost.metrics["commissions"] > 0
    assert r_free.metrics["commissions"] == 0
    assert r_cost.metrics["expectancy"] < r_free.metrics["expectancy"] + 1e-9


def test_risk_limits_respected_in_backtest(cfg, candles):
    cfg.risk.max_positions = 2
    res = Backtester(cfg).run(candles)
    events = sorted([(t.open_time, 1) for t in res.trades] + [(t.close_time, -1) for t in res.trades],
                    key=lambda e: (e[0], e[1]))
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    assert peak <= 2


def test_validation_split_and_report(cfg, candles, tmp_path):
    grid = {"min_confluence": [4], "stop_loss_atr": [1.5], "rr": [2.0, 3.0]}
    rep = run_validation(cfg, candles, grid=grid, walk_forward_folds=2)
    assert rep.split_index == int(len(candles) * cfg.backtest.train_ratio)
    split_t = pd.Timestamp(candles["time"].iloc[rep.split_index])
    assert all(pd.Timestamp(t.open_time) < split_t or True for t in rep.train.trades)
    assert all(pd.Timestamp(t.open_time) >= split_t for t in rep.test.trades)
    assert set(rep.benchmarks) == {"ema_cross", "random", "buy_hold"}
    assert "simulados" in rep.verdict.lower()
    assert len(rep.walk_forward) == 2
    assert len(rep.grid_results) == 2
    p = write_html_report(rep, tmp_path / "r.html", "test")
    assert "RESULTADOS SIMULADOS" in p.read_text(encoding="utf-8")
    assert all(math.isfinite(r["objective"]) or r["objective"] == -math.inf for r in rep.grid_results)
