"""Gestión de riesgo: tamaño de posición, límites de exposición y protecciones.

Política anti-martingala explícita:
* El tamaño SOLO depende del balance actual, del % de riesgo y de la
  distancia al Stop Loss. Nunca de pérdidas anteriores.
* No se añaden posiciones en una dirección que ya está en pérdida
  (``block_averaging_down``).
* No se duplican operaciones para la misma señal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from ..config import RiskConfig, StrategyConfig
from .simulator import MultiPositionSimulator


@dataclass
class RiskState:
    day: Optional[date] = None
    day_start_equity: float = 0.0
    peak_equity: float = 0.0
    daily_limit_hit: bool = False
    drawdown_limit_hit: bool = False
    emergency_stop: bool = False
    data_paused: bool = False
    volatility_block: bool = False
    pause_reason: str = ""
    used_signal_ids: set = field(default_factory=set)
    last_signal_bar: dict = field(default_factory=dict)  # side -> índice de barra


@dataclass
class RiskCheck:
    allowed: bool
    reason: str
    volume: float = 0.0


class RiskManager:
    def __init__(self, cfg: RiskConfig, strat: StrategyConfig | None = None, contract_size: float = 100.0) -> None:
        self.cfg = cfg
        self.strat = strat or StrategyConfig()
        self.contract_size = contract_size
        self.state = RiskState()

    # ----------------------------------------------------------------- estado
    def start(self, equity: float, now: datetime) -> None:
        self.state.day = now.date()
        self.state.day_start_equity = equity
        self.state.peak_equity = max(self.state.peak_equity, equity)

    @property
    def trading_blocked(self) -> bool:
        s = self.state
        return s.emergency_stop or s.data_paused or s.daily_limit_hit or s.drawdown_limit_hit

    def status_text(self) -> str:
        s = self.state
        if s.emergency_stop:
            return "PARADA DE EMERGENCIA"
        if s.data_paused:
            return f"PAUSA POR DATOS: {s.pause_reason}"
        if s.daily_limit_hit:
            return "LÍMITE DE PÉRDIDA DIARIA ALCANZADO"
        if s.drawdown_limit_hit:
            return "LÍMITE DE DRAWDOWN ALCANZADO"
        if s.volatility_block:
            return "VOLATILIDAD EXTREMA: ENTRADAS BLOQUEADAS"
        return "OPERATIVO"

    def daily_loss(self, equity: float) -> float:
        return max(0.0, self.state.day_start_equity - equity)

    def update(self, equity: float, now: datetime) -> list[str]:
        """Actualiza límites con la equity actual. Devuelve eventos disparados."""
        events: list[str] = []
        s = self.state
        if s.day != now.date():
            s.day = now.date()
            s.day_start_equity = equity
            if s.daily_limit_hit:
                s.daily_limit_hit = False
                events.append("NUEVO DÍA: límite diario restablecido")
        s.peak_equity = max(s.peak_equity, equity)
        limit = s.day_start_equity * self.cfg.daily_loss_limit_pct / 100.0
        if not s.daily_limit_hit and self.daily_loss(equity) >= limit > 0:
            s.daily_limit_hit = True
            events.append(f"LÍMITE DIARIO: pérdida {self.daily_loss(equity):.2f} >= {limit:.2f} USD")
        dd = (s.peak_equity - equity) / s.peak_equity * 100 if s.peak_equity > 0 else 0.0
        if not s.drawdown_limit_hit and dd >= self.cfg.max_drawdown_pct:
            s.drawdown_limit_hit = True
            events.append(f"DRAWDOWN MÁXIMO: {dd:.2f}% >= {self.cfg.max_drawdown_pct:.2f}%")
        return events

    def set_volatility(self, atr_ratio: float | None, tick_jump: float = 0.0) -> bool:
        extreme = (atr_ratio is not None and atr_ratio > self.cfg.extreme_volatility_ratio) or \
                  tick_jump > self.cfg.max_tick_jump_usd
        self.state.volatility_block = bool(extreme)
        return self.state.volatility_block

    def pause_for_data(self, reason: str) -> None:
        self.state.data_paused = True
        self.state.pause_reason = reason

    def resume_data(self) -> None:
        self.state.data_paused = False
        self.state.pause_reason = ""

    def emergency(self) -> None:
        self.state.emergency_stop = True

    def reset_emergency(self) -> None:
        self.state.emergency_stop = False

    def reset_limits(self, equity: float, now: datetime) -> None:
        self.state = RiskState()
        self.start(equity, now)

    # ---------------------------------------------------------- tamaño/lotes
    def position_size(self, balance: float, sl_distance: float) -> float:
        if sl_distance <= 0 or balance <= 0:
            return 0.0
        risk_usd = balance * self.cfg.risk_per_trade_pct / 100.0
        raw = risk_usd / (sl_distance * self.contract_size)
        step = self.cfg.lot_step
        lots = math.floor(raw / step + 1e-9) * step
        lots = min(lots, self.cfg.max_lot_per_trade)
        return round(lots, 2) if lots >= self.cfg.min_lot else 0.0

    def stop_distances(self, atr: float) -> tuple[float, float]:
        c = self.cfg
        sl = c.stop_loss_usd_points if c.stop_loss_usd_points > 0 else c.stop_loss_atr * atr
        tp = c.take_profit_usd_points if c.take_profit_usd_points > 0 else c.take_profit_atr * atr
        return sl, tp

    # ------------------------------------------------------------- permisos
    def check_entry(self, side: str, sim: MultiPositionSimulator, signal_id: str, price: float, atr: float,
                    spread: float, bar_index: int | None = None) -> RiskCheck:
        c, s = self.cfg, self.state
        if s.emergency_stop:
            return RiskCheck(False, "Parada de emergencia activa")
        if s.data_paused:
            return RiskCheck(False, f"Sistema en pausa por datos: {s.pause_reason}")
        if s.daily_limit_hit:
            return RiskCheck(False, "Límite de pérdida diaria alcanzado")
        if s.drawdown_limit_hit:
            return RiskCheck(False, "Límite de drawdown alcanzado")
        if s.volatility_block:
            return RiskCheck(False, "Volatilidad extrema: entradas bloqueadas")
        if signal_id and signal_id in s.used_signal_ids:
            return RiskCheck(False, "Señal duplicada: ya se abrió una posición con esta señal")
        if spread > c.max_spread_usd:
            return RiskCheck(False, f"Spread demasiado alto ({spread:.2f})")
        if len(sim.positions) >= c.max_positions:
            return RiskCheck(False, f"Máximo de posiciones simultáneas ({c.max_positions})")
        if sim.count_by_side(side) >= c.max_positions_per_side:
            return RiskCheck(False, f"Máximo de posiciones {side} ({c.max_positions_per_side})")
        if bar_index is not None and side in s.last_signal_bar:
            if bar_index - s.last_signal_bar[side] < self.strat.cooldown_bars:
                return RiskCheck(False, f"Enfriamiento: menos de {self.strat.cooldown_bars} velas desde la última entrada {side}")
        same = [p for p in sim.positions.values() if p.side == side]
        if c.block_averaging_down and any(p.net_pnl < 0 for p in same):
            return RiskCheck(False, "Anti-martingala: ya hay posiciones en pérdida en esta dirección")
        if atr > 0 and any(abs(p.entry_price - price) < self.strat.min_entry_distance_atr * atr for p in same):
            return RiskCheck(False, "Entrada demasiado cercana a otra posición en la misma dirección")
        sl_dist, _ = self.stop_distances(atr)
        vol = self.position_size(sim.balance, sl_dist)
        if vol <= 0:
            return RiskCheck(False, "El riesgo por operación no permite ni el lote mínimo con este SL")
        remaining = round(c.max_total_lots - sim.total_lots, 2)
        if remaining < c.min_lot:
            return RiskCheck(False, f"Exposición total máxima alcanzada ({c.max_total_lots} lotes)")
        vol = round(min(vol, remaining), 2)
        return RiskCheck(True, "OK", vol)

    def register_entry(self, side: str, signal_id: str, bar_index: int | None) -> None:
        if signal_id:
            self.state.used_signal_ids.add(signal_id)
        if bar_index is not None:
            self.state.last_signal_bar[side] = bar_index
