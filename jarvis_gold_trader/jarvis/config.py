"""Configuración editable del sistema (JSON <-> dataclasses) con validación."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

from .safety import SafetyViolation, TradingMode, assert_no_credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default_config.json"
USER_CONFIG_PATH = PROJECT_ROOT / "config" / "user_config.json"

VALID_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1")


@dataclass
class MarketConfig:
    symbol: str = "XAUUSD"
    symbol_variants: list[str] = field(default_factory=lambda: ["XAUUSD", "XAUUSDm", "XAUUSD.", "GOLD", "XAUUSD.a"])
    data_source: str = "synthetic"  # synthetic | mt5 | csv
    csv_path: str = ""
    analysis_timeframe: str = "M5"
    timeframes: list[str] = field(default_factory=lambda: list(VALID_TIMEFRAMES))
    history_bars: int = 600
    synthetic_seed: int = 7
    synthetic_start_price: float = 2350.0
    tick_interval_ms: int = 500
    sim_seconds_per_tick: int = 15  # tiempo de mercado simulado que avanza por tick


@dataclass
class IndicatorConfig:
    ema_fast: int = 9
    ema_mid: int = 21
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    volume_period: int = 20
    swing_lookback: int = 3
    sr_levels: int = 4
    use_volume: bool = True
    use_ema200_filter: bool = True
    use_rsi: bool = True
    use_macd: bool = True
    use_structure: bool = True


@dataclass
class StrategyConfig:
    min_confluence: int = 4  # nº mínimo de factores coincidentes (nunca 1 indicador)
    min_score: float = 60.0  # puntuación de confluencia mínima (0-100)
    max_extension_atr: float = 2.5  # filtro de sobre-extensión respecto a EMA21
    cooldown_bars: int = 3  # barras mínimas entre señales en la misma dirección
    min_entry_distance_atr: float = 0.75  # distancia mínima entre entradas iguales


@dataclass
class RiskConfig:
    initial_balance: float = 10000.0
    risk_per_trade_pct: float = 0.5
    max_positions: int = 5
    max_positions_per_side: int = 3
    max_total_lots: float = 1.0
    max_lot_per_trade: float = 0.20
    min_lot: float = 0.01
    lot_step: float = 0.01
    stop_loss_atr: float = 1.5
    take_profit_atr: float = 3.0
    stop_loss_usd_points: float = 0.0  # >0 fija SL en $ de precio en vez de ATR
    take_profit_usd_points: float = 0.0
    trailing_enabled: bool = True
    trailing_activation_atr: float = 1.0
    trailing_distance_atr: float = 1.0
    daily_loss_limit_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    extreme_volatility_ratio: float = 2.5  # ATR actual / mediana ATR
    max_tick_jump_usd: float = 15.0  # salto de precio entre ticks considerado error/extremo
    max_spread_usd: float = 1.0
    block_averaging_down: bool = True  # anti-martingala: no añadir a una dirección en pérdida


@dataclass
class CostConfig:
    contract_size: float = 100.0  # onzas por lote XAUUSD
    spread_usd: float = 0.30  # spread simulado cuando la fuente no lo provee
    commission_per_lot: float = 7.0  # USD por lote, ida y vuelta
    slippage_usd: float = 0.05  # deslizamiento adverso por ejecución


@dataclass
class SmartCloseConfig:
    enabled: bool = True
    individual_target_usd: float = 0.0  # 0 = desactivado
    group_target_usd: float = 150.0  # cierra todo si el neto flotante >= objetivo
    group_stop_usd: float = 300.0  # cierra todo si el neto flotante <= -valor
    close_positive_target_usd: float = 0.0  # cierra solo positivas cuando su suma >= objetivo
    max_bars_in_trade: int = 96  # cierre por tiempo (0 = desactivado)
    close_on_opposite_signal: bool = True


@dataclass
class BacktestConfig:
    bars: int = 6000
    train_ratio: float = 0.6
    min_trades_for_stats: int = 20
    seed: int = 11


@dataclass
class AppConfig:
    mode: str = TradingMode.SIMULATION.value
    database_path: str = "data/jarvis.db"
    market: MarketConfig = field(default_factory=MarketConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    smart_close: SmartCloseConfig = field(default_factory=SmartCloseConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    # ------------------------------------------------------------------ helpers
    @property
    def trading_mode(self) -> TradingMode:
        return TradingMode.parse(self.mode)

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        TradingMode.parse(self.mode)  # lanza si es LIVE
        assert_no_credentials(self.to_dict())
        m, r, s = self.market, self.risk, self.strategy
        errors: list[str] = []
        if m.analysis_timeframe not in VALID_TIMEFRAMES:
            errors.append(f"Temporalidad no válida: {m.analysis_timeframe}")
        for tf in m.timeframes:
            if tf not in VALID_TIMEFRAMES:
                errors.append(f"Temporalidad no válida: {tf}")
        if m.data_source not in ("synthetic", "mt5", "csv"):
            errors.append("data_source debe ser synthetic, mt5 o csv")
        mode = TradingMode.parse(self.mode)
        if m.data_source == "mt5" and mode != TradingMode.DEMO:
            errors.append("La fuente MetaTrader 5 requiere modo DEMO")
        if mode == TradingMode.DEMO and m.data_source != "mt5":
            errors.append("El modo DEMO usa datos de MetaTrader 5: seleccione data_source='mt5' o modo SIMULATION")
        if m.data_source == "csv" and not m.csv_path:
            errors.append("Indique la ruta del archivo CSV")
        if r.initial_balance <= 0:
            errors.append("El capital inicial debe ser > 0")
        if not 0 < r.risk_per_trade_pct <= 5:
            errors.append("El riesgo por operación debe estar entre 0 y 5 %")
        if not 1 <= r.max_positions <= 50:
            errors.append("max_positions debe estar entre 1 y 50")
        if r.max_positions_per_side > r.max_positions:
            errors.append("max_positions_per_side no puede superar max_positions")
        if r.max_lot_per_trade <= 0 or r.max_total_lots <= 0:
            errors.append("Los límites de lotes deben ser > 0")
        if r.stop_loss_atr <= 0 and r.stop_loss_usd_points <= 0:
            errors.append("Stop Loss obligatorio: defina stop_loss_atr o stop_loss_usd_points")
        if not 0 < r.daily_loss_limit_pct <= 50:
            errors.append("El límite de pérdida diaria debe estar entre 0 y 50 %")
        if s.min_confluence < 2:
            errors.append("min_confluence debe ser >= 2: nunca se opera con un único indicador")
        if not 0 < self.backtest.train_ratio < 1:
            errors.append("train_ratio debe estar entre 0 y 1")
        if errors:
            raise ValueError("Configuración inválida:\n- " + "\n- ".join(errors))


def _build(cls, data: dict | None):
    """Construye un dataclass a partir de un dict ignorando claves desconocidas."""
    obj = cls()
    if not data:
        return obj
    for f in fields(cls):
        if f.name not in data:
            continue
        current = getattr(obj, f.name)
        value = data[f.name]
        if is_dataclass(current):
            setattr(obj, f.name, _build(type(current), value))
        elif isinstance(current, bool):
            setattr(obj, f.name, bool(value))
        elif isinstance(current, int) and not isinstance(current, bool):
            setattr(obj, f.name, int(value))
        elif isinstance(current, float):
            setattr(obj, f.name, float(value))
        else:
            setattr(obj, f.name, value)
    return obj


def config_from_dict(data: dict) -> AppConfig:
    if "mode" in data:
        TradingMode.parse(data["mode"])
    assert_no_credentials(data)
    cfg = _build(AppConfig, data)
    cfg.validate()
    return cfg


def load_config(path: str | Path | None = None) -> AppConfig:
    """Carga user_config.json si existe; si no, default_config.json; si no, valores por defecto."""
    candidates = [Path(path)] if path else [USER_CONFIG_PATH, DEFAULT_CONFIG_PATH]
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                return config_from_dict(json.load(fh))
    cfg = AppConfig()
    cfg.validate()
    return cfg


def save_config(cfg: AppConfig, path: str | Path | None = None) -> Path:
    cfg.validate()
    p = Path(path) if path else USER_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg.to_dict(), fh, indent=2, ensure_ascii=False)
    return p


def resolve_path(relative: str) -> Path:
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p


__all__ = [
    "AppConfig", "MarketConfig", "IndicatorConfig", "StrategyConfig", "RiskConfig", "CostConfig",
    "SmartCloseConfig", "BacktestConfig", "load_config", "save_config", "config_from_dict",
    "VALID_TIMEFRAMES", "SafetyViolation", "resolve_path", "PROJECT_ROOT",
]
