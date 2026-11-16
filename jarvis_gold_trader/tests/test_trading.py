from datetime import timedelta

import pytest

from conftest import T0
from jarvis.config import RiskConfig, SmartCloseConfig, StrategyConfig
from jarvis.trading import CostModel, MultiPositionSimulator, RiskManager, SmartCloseManager


@pytest.fixture
def costs():
    return CostModel(contract_size=100, spread=0.3, commission_per_lot=7, slippage=0.05)


@pytest.fixture
def sim(costs):
    return MultiPositionSimulator(10000, costs, RiskConfig(trailing_enabled=False))


def test_pnl_includes_spread_commission_slippage(sim):
    p = sim.open_position("BUY", 0.10, 1990, 2020, 2000.0, 2000.3, T0)
    assert p.entry_price == pytest.approx(2000.35)
    sim.on_tick(2000.0, 2000.3, T0)
    # marcado al bid: (2000 - 2000.35) * 0.1 * 100 = -3.5 ; comisión 0.7
    assert p.net_pnl == pytest.approx(-3.5 - 0.7)
    t = sim.close_position(p.id, 2010.0, 2010.3, T0, "TEST")
    assert t.exit_price == pytest.approx(2009.95)
    assert t.net_pnl == pytest.approx((2009.95 - 2000.35) * 10 - 0.7)
    assert sim.balance == pytest.approx(10000 + t.net_pnl)


def test_sell_pnl_direction(sim):
    p = sim.open_position("SELL", 0.10, 2010, 1990, 2000.0, 2000.3, T0)
    t = sim.close_position(p.id, 1995.0, 1995.3, T0, "TEST")
    assert t.gross_pnl > 0


def test_stop_loss_and_take_profit(sim):
    a = sim.open_position("BUY", 0.1, 1995, 2010, 2000, 2000.3, T0)
    b = sim.open_position("SELL", 0.1, 2010, 1990, 2000, 2000.3, T0)
    closed = sim.on_tick(1994.0, 1994.3, T0)
    reasons = {t.id: t.reason for t in closed}
    assert reasons[a.id] == "STOP LOSS"
    assert b.id in sim.positions
    closed = sim.on_tick(1989.5, 1989.8, T0)
    assert closed[0].reason == "TAKE PROFIT"


def test_trailing_stop_moves_only_favourably(costs):
    s = MultiPositionSimulator(10000, costs, RiskConfig(trailing_enabled=True, trailing_activation_atr=1,
                                                        trailing_distance_atr=1))
    p = s.open_position("BUY", 0.1, 1990, 2100, 2000, 2000.3, T0, atr=2.0)
    s.on_tick(2005, 2005.3, T0)
    assert p.sl == pytest.approx(2003.0)
    s.on_tick(2004, 2004.3, T0)
    assert p.sl == pytest.approx(2003.0)
    closed = s.on_tick(2002.9, 2003.2, T0)
    assert closed and closed[0].reason == "TRAILING STOP"


def test_invalid_sl_rejected(sim):
    with pytest.raises(ValueError):
        sim.open_position("BUY", 0.1, 2005, 2010, 2000, 2000.3, T0)


def test_position_size_depends_only_on_balance_and_sl():
    rm = RiskManager(RiskConfig(risk_per_trade_pct=1.0, max_lot_per_trade=5), contract_size=100)
    assert rm.position_size(10000, 5.0) == pytest.approx(0.20)  # 100$ / (5*100)
    # sin martingala: el tamaño no crece tras pérdidas (menor balance -> menor o igual lote)
    assert rm.position_size(9000, 5.0) <= rm.position_size(10000, 5.0)
    assert rm.position_size(10000, 1000.0) == 0.0  # ni el lote mínimo cabe en el riesgo


def _rm(**kw):
    rc = RiskConfig(**{"max_positions": 3, "max_positions_per_side": 2, "max_total_lots": 1.0, **kw})
    return RiskManager(rc, StrategyConfig(cooldown_bars=0, min_entry_distance_atr=0), 100)


def test_risk_limits_positions_duplicates_and_exposure(sim):
    rm = _rm()
    rm.start(sim.equity, T0)
    ok = rm.check_entry("BUY", sim, "S1", 2000, 3, 0.3)
    assert ok.allowed and ok.volume > 0
    sim.open_position("BUY", ok.volume, 1990, 2020, 2000, 2000.3, T0)
    rm.register_entry("BUY", "S1", 1)
    assert not rm.check_entry("BUY", sim, "S1", 2000, 3, 0.3).allowed  # duplicada
    sim.on_tick(2001, 2001.3, T0)
    sim.open_position("BUY", 0.1, 1990, 2020, 2001, 2001.3, T0)
    r = rm.check_entry("BUY", sim, "S3", 2002, 3, 0.3)
    assert not r.allowed and "BUY" in r.reason  # máximo por dirección
    assert not rm.check_entry("SELL", sim, "S4", 2002, 3, 5.0).allowed  # spread alto


def test_total_exposure_cap(sim):
    rm = _rm(max_total_lots=0.25, max_positions=10, max_positions_per_side=10)
    rm.start(sim.equity, T0)
    sim.open_position("SELL", 0.25, 2010, 1990, 2000, 2000.3, T0)
    r = rm.check_entry("BUY", sim, "X", 2000, 3, 0.3)
    assert not r.allowed and "Exposición" in r.reason


def test_anti_martingale_blocks_averaging_down(sim):
    rm = _rm()
    rm.start(sim.equity, T0)
    sim.open_position("BUY", 0.1, 1980, 2020, 2000, 2000.3, T0)
    sim.on_tick(1995, 1995.3, T0)  # posición en pérdida
    r = rm.check_entry("BUY", sim, "B2", 1995, 3, 0.3)
    assert not r.allowed and "martingala" in r.reason.lower()
    assert rm.check_entry("SELL", sim, "S2", 1995, 3, 0.3).allowed


def test_daily_loss_limit_and_reset(sim):
    rm = _rm(daily_loss_limit_pct=1.0)
    rm.start(10000, T0)
    events = rm.update(9890, T0 + timedelta(hours=1))
    assert rm.state.daily_limit_hit and events
    assert not rm.check_entry("BUY", sim, "Z", 2000, 3, 0.3).allowed
    rm.update(9890, T0 + timedelta(days=1))
    assert not rm.state.daily_limit_hit


def test_volatility_and_emergency_block(sim):
    rm = _rm()
    rm.start(10000, T0)
    rm.set_volatility(3.0)
    assert not rm.check_entry("BUY", sim, "V", 2000, 3, 0.3).allowed
    rm.set_volatility(1.0)
    rm.emergency()
    assert "emergencia" in rm.check_entry("BUY", sim, "E", 2000, 3, 0.3).reason.lower()


def _two_positions(sim):
    a = sim.open_position("BUY", 0.1, 1980, 2100, 2000, 2000.3, T0)
    b = sim.open_position("SELL", 0.1, 2100, 1900, 2000, 2000.3, T0)
    return a, b


def test_smart_close_group_target(sim):
    _two_positions(sim)
    sim.open_position("BUY", 0.5, 1980, 2100, 2000, 2000.3, T0)
    sim.on_tick(2010, 2010.3, T0)
    sc = SmartCloseManager(SmartCloseConfig(group_target_usd=100, group_stop_usd=0, max_bars_in_trade=0))
    closed = sc.evaluate(sim, T0)
    assert len(closed) == 3 and not sim.positions
    assert all(t.reason == "OBJETIVO DE GRUPO" for t in closed)


def test_smart_close_group_stop(sim):
    sim.open_position("BUY", 0.5, 1900, 2100, 2000, 2000.3, T0)
    sim.on_tick(1990, 1990.3, T0)
    sc = SmartCloseManager(SmartCloseConfig(group_target_usd=0, group_stop_usd=200, max_bars_in_trade=0))
    assert sc.evaluate(sim, T0)[0].reason == "STOP DE GRUPO"


def test_smart_close_positives_individual_time_and_opposite(sim):
    a, b = _two_positions(sim)
    sim.on_tick(2010, 2010.3, T0)  # BUY gana, SELL pierde
    sc = SmartCloseManager(SmartCloseConfig(group_target_usd=0, group_stop_usd=0, close_positive_target_usd=50,
                                            max_bars_in_trade=0, close_on_opposite_signal=False))
    closed = sc.evaluate(sim, T0)
    assert [t.id for t in closed] == [a.id] and b.id in sim.positions
    sc.cfg = SmartCloseConfig(group_target_usd=0, group_stop_usd=0, max_bars_in_trade=2,
                              close_on_opposite_signal=False)
    sim.on_bar_closed(); sim.on_bar_closed()
    assert sc.evaluate(sim, T0)[0].reason == "TIEMPO MÁXIMO"
    c = sim.open_position("SELL", 0.1, 2100, 1900, 2010, 2010.3, T0)
    sc.cfg = SmartCloseConfig(group_target_usd=0, group_stop_usd=0, max_bars_in_trade=0, close_on_opposite_signal=True)
    assert sc.evaluate(sim, T0, opposite_signal_side="BUY")[0].id == c.id
    d = sim.open_position("BUY", 0.1, 1900, 2100, 2010, 2010.3, T0)
    sim.on_tick(2030, 2030.3, T0)
    sc.cfg = SmartCloseConfig(group_target_usd=0, group_stop_usd=0, individual_target_usd=100, max_bars_in_trade=0)
    assert sc.evaluate(sim, T0)[0].reason == "OBJETIVO INDIVIDUAL" and d.id not in sim.positions


def test_close_positive_negative_all(sim):
    _two_positions(sim)
    sim.on_tick(2010, 2010.3, T0)
    assert len(sim.close_positive(T0)) == 1
    assert len(sim.close_negative(T0)) == 1
    _two_positions(sim)
    assert len(sim.close_all(T0, "x")) == 2 and sim.equity == sim.balance
