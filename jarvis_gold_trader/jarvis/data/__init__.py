"""Fuentes de datos de mercado (sintética, MetaTrader 5 DEMO, CSV histórico)."""

from __future__ import annotations

from .base import TIMEFRAME_MINUTES, DataError, MarketDataProvider, Tick, resample_candles
from .csv_provider import CSVReplayProvider, load_candles_csv
from .mt5_provider import MT5DemoProvider
from .synthetic import SyntheticGoldProvider, generate_synthetic_candles


def create_provider(config) -> MarketDataProvider:
    """Fábrica de proveedores a partir de ``AppConfig``."""
    from ..config import resolve_path

    m = config.market
    if m.data_source == "mt5":
        return MT5DemoProvider(symbol_variants=m.symbol_variants)
    if m.data_source == "csv":
        return CSVReplayProvider(resolve_path(m.csv_path), spread=config.costs.spread_usd, symbol=m.symbol)
    minutes = TIMEFRAME_MINUTES.get(m.analysis_timeframe, 5)
    history = max(15000, (m.history_bars + 260) * minutes)
    return SyntheticGoldProvider(seed=m.synthetic_seed, start_price=m.synthetic_start_price,
                                 history_minutes=history, seconds_per_tick=m.sim_seconds_per_tick,
                                 base_spread=config.costs.spread_usd * 0.8, symbol=m.symbol)


__all__ = ["Tick", "DataError", "MarketDataProvider", "SyntheticGoldProvider", "MT5DemoProvider",
           "CSVReplayProvider", "load_candles_csv", "generate_synthetic_candles", "create_provider",
           "TIMEFRAME_MINUTES", "resample_candles"]
