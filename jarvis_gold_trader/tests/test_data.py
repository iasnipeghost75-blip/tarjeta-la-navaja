from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from jarvis.data import CSVReplayProvider, DataError, MT5DemoProvider, SyntheticGoldProvider, resample_candles
from jarvis.data.validation import validate_candles, validate_tick
from jarvis.data.base import Tick
from jarvis.safety import SafetyViolation
from conftest import T0


def test_synthetic_is_deterministic():
    a = SyntheticGoldProvider(seed=3, history_minutes=2000)
    b = SyntheticGoldProvider(seed=3, history_minutes=2000)
    a.connect(); b.connect()
    assert a.get_candles("M5", 100).equals(b.get_candles("M5", 100))
    assert a.step() == b.step()


def test_synthetic_candles_valid_and_ticks_coherent():
    p = SyntheticGoldProvider(seed=5, history_minutes=3000)
    p.connect()
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        df = p.get_candles(tf, 40)
        assert validate_candles(df) == []
    prev = None
    for _ in range(50):
        t = p.step()
        assert t.ask > t.bid > 0
        assert validate_tick(t, prev, 5, 50) == []
        prev = t


def test_only_closed_candles_returned():
    p = SyntheticGoldProvider(seed=5, history_minutes=3000, seconds_per_tick=15)
    p.connect()
    for _ in range(7):
        p.step()
    df = p.get_candles("M5", 50)
    last_end = df["time"].iloc[-1] + pd.Timedelta(minutes=5)
    assert last_end <= pd.Timestamp(p.now)
    with_forming = p.get_candles("M5", 50, include_forming=True)
    assert with_forming["time"].iloc[-1] > df["time"].iloc[-1]


def test_resample_matches_manual():
    p = SyntheticGoldProvider(seed=1, history_minutes=600)
    p.connect()
    m1 = p._m1_frame()
    m5 = resample_candles(m1, "M5")
    first = m1[m1["time"] < m5["time"].iloc[0] + pd.Timedelta(minutes=5)]
    assert m5["high"].iloc[0] == first["high"].max()
    assert m5["volume"].iloc[0] == first["volume"].sum()


def test_validation_detects_corruption(candles):
    bad = candles.head(50).copy()
    bad.loc[10, "high"] = bad.loc[10, "low"] - 1
    assert validate_candles(bad)
    assert validate_tick(Tick(T0, float("nan"), float("nan")), None, 1, 10)
    assert validate_tick(Tick(T0, 2000, 1999), None, 1, 10)


def test_injected_data_error_produces_invalid_tick():
    p = SyntheticGoldProvider(seed=1, history_minutes=600)
    p.connect()
    p.inject_data_error()
    assert np.isnan(p.step().bid)


def test_csv_replay_no_future_data(tmp_path, candles):
    path = tmp_path / "x.csv"
    candles.head(800).to_csv(path, index=False)
    prov = CSVReplayProvider(path, warmup_bars=300)
    prov.connect()
    tick = prov.step()
    visible = prov.get_candles("M5", 1000)
    assert visible["time"].iloc[-1] <= pd.Timestamp(tick.time)
    assert len(visible) == 301
    assert len(prov.get_candles("M15", 1000)) > 0


def test_csv_mt5_export_format(tmp_path):
    path = tmp_path / "mt5.csv"
    path.write_text("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n"
                    + "".join(f"2026.01.05\t10:{m:02d}:00\t2000\t2001\t1999\t2000.5\t10\n" for m in range(30)))
    from jarvis.data import load_candles_csv
    df = load_candles_csv(path)
    assert len(df) == 30 and df["volume"].iloc[0] == 10


def _fake_mt5(trade_mode, symbols=("XAUUSDm",)):
    rates = np.array([(1767607200 + 300 * i, 2000.0 + i, 2001.0 + i, 1999.0 + i, 2000.5 + i, 100, 20, 0)
                      for i in range(10)],
                     dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"),
                            ("tick_volume", "i8"), ("spread", "i4"), ("real_volume", "i8")])
    calls = {"shutdown": 0}

    class M:
        ACCOUNT_TRADE_MODE_DEMO = 0
        TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_M30, TIMEFRAME_H1 = 1, 5, 15, 30, 16385
        initialize = staticmethod(lambda *a, **k: True)
        last_error = staticmethod(lambda: (0, "ok"))
        account_info = staticmethod(lambda: SimpleNamespace(trade_mode=trade_mode, login=1, server="Demo",
                                                             currency="USD", balance=1e4, leverage=100))
        symbol_info = staticmethod(lambda n: SimpleNamespace(visible=True) if n in symbols else None)
        symbol_select = staticmethod(lambda n, v: True)
        symbols_get = staticmethod(lambda g: [])
        symbol_info_tick = staticmethod(lambda n: SimpleNamespace(time=1767607200, bid=2000.1, ask=2000.4, volume=0))
        copy_rates_from_pos = staticmethod(lambda s, tf, pos, n: rates[-n:])

        @staticmethod
        def shutdown():
            calls["shutdown"] += 1
    return M, calls


def test_mt5_demo_account_and_symbol_variant():
    m, _ = _fake_mt5(trade_mode=0)
    prov = MT5DemoProvider(["XAUUSD", "XAUUSDm"], mt5_module=m)
    prov.connect()
    assert prov.symbol == "XAUUSDm"
    t = prov.step()
    assert t.ask > t.bid
    df = prov.get_candles("M5", 5)
    assert len(df) == 5 and list(df.columns) == ["time", "open", "high", "low", "close", "volume"]


def test_mt5_real_account_is_refused():
    m, calls = _fake_mt5(trade_mode=2)  # ACCOUNT_TRADE_MODE_REAL
    prov = MT5DemoProvider(mt5_module=m)
    with pytest.raises(SafetyViolation):
        prov.connect()
    assert calls["shutdown"] == 1 and not prov.connected


def test_mt5_missing_symbol():
    m, _ = _fake_mt5(trade_mode=0, symbols=())
    with pytest.raises(DataError):
        MT5DemoProvider(mt5_module=m).connect()
