import pytest

from jarvis.analysis import ConfidenceCalibrator
from jarvis.core import TradingController
from jarvis.data import SyntheticGoldProvider


@pytest.fixture
def ctrl(cfg, db):
    cfg.market.history_bars = 400
    p = SyntheticGoldProvider(seed=7, history_minutes=6000, seconds_per_tick=60)
    c = TradingController(cfg, provider=p, db=db)
    c.start()
    return c


def test_run_loop_persists_everything(ctrl, db):
    for _ in range(900):
        ctrl.step()
    s = ctrl.snapshot()
    assert s["mode"] == "SIMULATION" and s["ticks"] == 900
    assert ctrl.analysis is not None and len(ctrl.signals) > 0
    assert len(db.signals()) == len(ctrl.signals)
    assert len(db.trades(ctrl.session_id)) == len(ctrl.sim.closed)
    assert len(db.equity(ctrl.session_id)) > 0
    assert len(db.decisions(ctrl.session_id)) > 0
    assert len(ctrl.sim.positions) <= ctrl.cfg.risk.max_positions
    assert ctrl.sim.total_lots <= ctrl.cfg.risk.max_total_lots + 1e-9
    ids = [r.signal.id for r in ctrl.signals if r.accepted]
    assert len(ids) == len(set(ids))  # nunca se duplica una señal


def test_manual_trade_and_closes(ctrl):
    ok, _ = ctrl.manual_open("BUY")
    assert ok and len(ctrl.sim.positions) == 1
    pid = next(iter(ctrl.sim.positions))
    assert ctrl.close_position(pid).reason == "CIERRE MANUAL"
    ctrl.manual_open("BUY")
    ctrl.manual_open("SELL")
    assert len(ctrl.close_all()) == len(ctrl.db.trades(ctrl.session_id)) - 1


def test_emergency_stop(ctrl):
    ctrl.manual_open("BUY")
    closed = ctrl.emergency_stop()
    assert closed and not ctrl.sim.positions and not ctrl.auto_trading
    ok, msg = ctrl.manual_open("SELL")
    assert not ok and "emergencia" in msg.lower()
    ctrl.reset_emergency()
    assert ctrl.manual_open("SELL")[0]


def test_data_error_pauses_and_resumes(ctrl):
    ctrl.inject_data_error()
    ctrl.step()
    assert ctrl.snapshot()["data_paused"]
    assert not ctrl.manual_open("BUY")[0]
    ctrl.step()
    assert ctrl.snapshot()["data_paused"]  # la reanudación es manual
    assert ctrl.resume_after_data_pause()
    assert not ctrl.snapshot()["data_paused"]


def test_volatility_spike_blocks_entries(ctrl):
    ctrl.inject_volatility_spike(40)
    ctrl.step()
    assert ctrl.risk.state.volatility_block
    assert not ctrl.manual_open("BUY")[0]


def test_daily_loss_limit_closes_everything(ctrl):
    ctrl.manual_open("BUY")
    ctrl.risk.state.day_start_equity = ctrl.sim.equity + ctrl.sim.equity * 0.05  # simula pérdida del 5 %
    ctrl.step()
    assert ctrl.risk.state.daily_limit_hit and not ctrl.sim.positions


def test_apply_config_and_reset(ctrl):
    import copy
    new = copy.deepcopy(ctrl.cfg)
    new.risk.max_positions = 2
    new.risk.initial_balance = 5000
    warnings = ctrl.apply_config(new)
    assert ctrl.risk.cfg.max_positions == 2 and warnings
    ctrl.reset_account()
    assert ctrl.sim.balance == 5000 and ctrl.sim.initial_balance == 5000


def test_calibrator_persisted(ctrl, db):
    cal = ConfidenceCalibrator(min_trades=2).fit([(70, 5), (70, -2), (70, 3)], "test")
    ctrl.set_calibrator(cal)
    assert ConfidenceCalibrator.from_dict(db.get_kv("calibration")).total.n == 3


def test_auto_trading_off_rejects_signals(ctrl):
    ctrl.set_auto_trading(False)
    for _ in range(600):
        ctrl.step()
    assert all(not r.accepted for r in ctrl.signals)
