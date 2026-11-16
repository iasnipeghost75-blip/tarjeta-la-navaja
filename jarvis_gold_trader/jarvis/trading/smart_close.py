"""Cierre inteligente: supervisa las posiciones y decide cierres individuales o de grupo.

Cada decisión (incluida la de NO cerrar cuando un objetivo se evalúa) queda
registrada con su motivo para poder auditarla en el historial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..config import SmartCloseConfig
from .models import ClosedTrade
from .simulator import MultiPositionSimulator


@dataclass
class PortfolioView:
    positives: list[int]
    negatives: list[int]
    net_positive: float
    net_negative: float
    net_total: float


def portfolio_view(sim: MultiPositionSimulator) -> PortfolioView:
    pos = [p for p in sim.positions.values() if p.net_pnl > 0]
    neg = [p for p in sim.positions.values() if p.net_pnl <= 0]
    return PortfolioView([p.id for p in pos], [p.id for p in neg], sum(p.net_pnl for p in pos),
                         sum(p.net_pnl for p in neg), sim.floating_pnl)


class SmartCloseManager:
    def __init__(self, cfg: SmartCloseConfig) -> None:
        self.cfg = cfg

    def evaluate(self, sim: MultiPositionSimulator, time: datetime,
                 opposite_signal_side: Optional[str] = None) -> list[ClosedTrade]:
        c = self.cfg
        if not c.enabled or not sim.positions:
            return []
        view = portfolio_view(sim)
        log = sim._log
        # 1) Objetivo de grupo (neto después de costes)
        if c.group_target_usd > 0 and view.net_total >= c.group_target_usd:
            log(time, "SMART_CLOSE", "OBJETIVO DE GRUPO",
                f"Neto flotante {view.net_total:+.2f} >= objetivo {c.group_target_usd:.2f}: cierre de todas "
                f"({len(sim.positions)} posiciones)")
            return sim.close_all(time, "OBJETIVO DE GRUPO")
        # 2) Stop de grupo
        if c.group_stop_usd > 0 and view.net_total <= -c.group_stop_usd:
            log(time, "SMART_CLOSE", "STOP DE GRUPO",
                f"Neto flotante {view.net_total:+.2f} <= -{c.group_stop_usd:.2f}: cierre de todas")
            return sim.close_all(time, "STOP DE GRUPO")
        out: list[ClosedTrade] = []
        # 3) Cierre de posiciones positivas cuando su suma alcanza el objetivo
        if c.close_positive_target_usd > 0 and view.positives and view.net_positive >= c.close_positive_target_usd:
            log(time, "SMART_CLOSE", "CIERRE POSITIVAS",
                f"Suma de positivas {view.net_positive:+.2f} >= {c.close_positive_target_usd:.2f}: "
                f"cierre de {len(view.positives)} posiciones")
            out += sim.close_many(view.positives, time, "OBJETIVO POSITIVAS")
        # 4) Objetivo individual neto
        if c.individual_target_usd > 0:
            for p in list(sim.positions.values()):
                if p.net_pnl >= c.individual_target_usd:
                    log(time, "SMART_CLOSE", "OBJETIVO INDIVIDUAL",
                        f"#{p.id} neto {p.net_pnl:+.2f} >= {c.individual_target_usd:.2f}", p.id)
                    out += sim.close_many([p.id], time, "OBJETIVO INDIVIDUAL")
        # 5) Cierre por tiempo
        if c.max_bars_in_trade > 0:
            for p in list(sim.positions.values()):
                if p.bars_held >= c.max_bars_in_trade:
                    log(time, "SMART_CLOSE", "CIERRE POR TIEMPO",
                        f"#{p.id} lleva {p.bars_held} velas (máx {c.max_bars_in_trade})", p.id)
                    out += sim.close_many([p.id], time, "TIEMPO MÁXIMO")
        # 6) Señal contraria confirmada
        if c.close_on_opposite_signal and opposite_signal_side:
            against = "SELL" if opposite_signal_side == "BUY" else "BUY"
            ids = [p.id for p in sim.positions.values() if p.side == against]
            if ids:
                log(time, "SMART_CLOSE", "SEÑAL CONTRARIA",
                    f"Señal {opposite_signal_side} confirmada: cierre de {len(ids)} posiciones {against}")
                out += sim.close_many(ids, time, "SEÑAL CONTRARIA")
        return out
