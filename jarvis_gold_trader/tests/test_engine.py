import pandas as pd

from jarvis.analysis import AnalysisEngine, ConfidenceCalibrator, wilson_interval
from jarvis.config import StrategyConfig


def test_signals_require_min_confluence(candles):
    eng = AnalysisEngine(strat_cfg=StrategyConfig(min_confluence=4))
    f = eng.compute_features(candles)
    for side in ("long", "short"):
        sig = f[f[f"{side}_signal"]]
        assert len(sig) > 0
        assert (sig[f"{side}_count"] >= 4).all()
        assert (sig[f"{side}_score"] >= eng.sc.min_score).all()
        assert (sig[f"{side}_filters"] == "").all()
        assert sig[f"{side}_f_ema_alignment"].all()


def test_never_single_indicator(candles):
    f = AnalysisEngine(strat_cfg=StrategyConfig(min_confluence=2, min_score=0)).compute_features(candles)
    assert (f.loc[f["long_signal"], "long_count"] >= 2).all()


def test_filters_block_signals(candles):
    f = AnalysisEngine().compute_features(candles)
    blocked = f["long_trigger"] & (f["long_filters"] != "")
    assert not (blocked & f["long_signal"]).any()


def test_analyze_output(candles):
    eng = AnalysisEngine()
    a = eng.analyze(candles, "M5")
    assert a.trend in ("alcista", "bajista", "lateral")
    assert 0 <= a.long_eval.score <= 100 and 0 <= a.short_eval.score <= 100
    assert a.volatility_state in ("baja", "normal", "alta", "extrema")
    assert a.summary_lines()


def test_signal_explanation_and_id(candles):
    eng = AnalysisEngine()
    f = eng.compute_features(candles)
    idx = f.index[f["long_signal"] | f["short_signal"]][-1]
    a = eng.analyze(candles.iloc[: idx + 1], "M5")
    assert a.signal is not None
    assert a.signal.id.startswith(a.signal.side)
    assert "factores" in a.signal.explanation
    assert pd.Timestamp(a.signal.time) == pd.Timestamp(candles["time"].iloc[idx])


def test_calibrator_insufficient_and_wilson():
    cal = ConfidenceCalibrator(min_trades=20)
    assert not cal.estimate(75)["sufficient"]
    cal.fit([(75, 10)] * 15 + [(75, -10)] * 10, "test")
    e = cal.estimate(75)
    assert e["sufficient"] and abs(e["win_rate"] - 0.6) < 1e-9
    assert e["ci_low"] < 0.6 < e["ci_high"]
    lo, hi = wilson_interval(0, 10)
    assert lo == 0 and 0 < hi < 0.35
    assert ConfidenceCalibrator.from_dict(cal.to_dict()).estimate(75)["n"] == 25
