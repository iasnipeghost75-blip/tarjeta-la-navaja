"""Modelo de costes simulados: spread, comisión y deslizamiento."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import CostConfig


@dataclass
class CostModel:
    contract_size: float = 100.0
    spread: float = 0.30
    commission_per_lot: float = 7.0
    slippage: float = 0.05

    @classmethod
    def from_config(cls, c: CostConfig) -> "CostModel":
        return cls(c.contract_size, c.spread_usd, c.commission_per_lot, c.slippage_usd)

    def entry_price(self, side: str, bid: float, ask: float) -> float:
        """Compra al Ask, vende al Bid, siempre con deslizamiento adverso."""
        return ask + self.slippage if side == "BUY" else bid - self.slippage

    def exit_price(self, side: str, bid: float, ask: float) -> float:
        return bid - self.slippage if side == "BUY" else ask + self.slippage

    def mark_price(self, side: str, bid: float, ask: float) -> float:
        return bid if side == "BUY" else ask

    def commission(self, volume: float) -> float:
        return self.commission_per_lot * volume

    def pnl(self, side: str, entry: float, price: float, volume: float) -> float:
        d = 1 if side == "BUY" else -1
        return (price - entry) * d * volume * self.contract_size

    def quotes_from_mid(self, mid: float) -> tuple[float, float]:
        return mid - self.spread / 2, mid + self.spread / 2
