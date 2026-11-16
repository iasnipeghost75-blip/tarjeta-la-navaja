"""Modelos de datos del simulador."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    id: int
    side: str  # BUY | SELL
    volume: float
    entry_price: float
    sl: float
    tp: float
    open_time: datetime
    signal_id: str = ""
    score: float = 0.0
    atr: float = 0.0
    commission: float = 0.0  # coste ida y vuelta estimado (se liquida al cerrar)
    current_price: float = 0.0
    gross_pnl: float = 0.0
    best_price: float = 0.0
    trailing_active: bool = False
    bars_held: int = 0
    initial_sl: float = 0.0
    mae: float = 0.0  # peor P&L flotante
    mfe: float = 0.0  # mejor P&L flotante

    @property
    def direction(self) -> int:
        return 1 if self.side == "BUY" else -1

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.commission

    def to_dict(self) -> dict:
        d = asdict(self)
        d["net_pnl"] = self.net_pnl
        return d


@dataclass
class ClosedTrade:
    id: int
    side: str
    volume: float
    entry_price: float
    exit_price: float
    open_time: datetime
    close_time: datetime
    gross_pnl: float
    commission: float
    net_pnl: float
    reason: str
    score: float = 0.0
    signal_id: str = ""
    sl: float = 0.0
    tp: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0

    @property
    def duration_seconds(self) -> float:
        return (self.close_time - self.open_time).total_seconds()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_seconds"] = self.duration_seconds
        return d


@dataclass
class Decision:
    time: datetime
    category: str  # SIGNAL | OPEN | CLOSE | RISK | SYSTEM | SMART_CLOSE
    action: str
    detail: str
    position_id: Optional[int] = None
    extra: dict = field(default_factory=dict)
