"""Simulador multioperación: posiciones independientes, SL/TP, trailing y cierres.

No existe conexión con ningún bróker: todas las aperturas y cierres son
asientos contables locales sobre un balance DEMO ficticio.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Optional

from ..config import RiskConfig
from ..safety import assert_simulated_execution
from .costs import CostModel
from .models import ClosedTrade, Decision, Position


class MultiPositionSimulator:
    def __init__(self, initial_balance: float, costs: CostModel, risk_cfg: RiskConfig | None = None,
                 on_decision: Optional[Callable[[Decision], None]] = None) -> None:
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.costs = costs
        self.rc = risk_cfg or RiskConfig()
        self.positions: dict[int, Position] = {}
        self.closed: list[ClosedTrade] = []
        self._next_id = 1
        self.on_decision = on_decision
        self.last_bid = 0.0
        self.last_ask = 0.0
        self.last_time: Optional[datetime] = None

    # ----------------------------------------------------------------- métricas
    @property
    def floating_pnl(self) -> float:
        return sum(p.net_pnl for p in self.positions.values())

    @property
    def equity(self) -> float:
        return self.balance + self.floating_pnl

    @property
    def total_lots(self) -> float:
        return round(sum(p.volume for p in self.positions.values()), 4)

    def lots_by_side(self, side: str) -> float:
        return round(sum(p.volume for p in self.positions.values() if p.side == side), 4)

    def count_by_side(self, side: str) -> int:
        return sum(1 for p in self.positions.values() if p.side == side)

    def _log(self, time, category, action, detail, pid=None, **extra) -> None:
        if self.on_decision:
            self.on_decision(Decision(time, category, action, detail, pid, extra))

    # ---------------------------------------------------------------- apertura
    def open_position(self, side: str, volume: float, sl: float, tp: float, bid: float, ask: float,
                      time: datetime, signal_id: str = "", score: float = 0.0, atr: float = 0.0,
                      entry_override: float | None = None) -> Position:
        assert_simulated_execution()
        if side not in ("BUY", "SELL"):
            raise ValueError("side debe ser BUY o SELL")
        if volume <= 0:
            raise ValueError("volumen debe ser > 0")
        if bid > 0 and ask > 0:
            self.last_bid, self.last_ask, self.last_time = bid, ask, time
        entry = entry_override if entry_override is not None else self.costs.entry_price(side, bid, ask)
        if side == "BUY" and not (sl < entry):
            raise ValueError("Para BUY el SL debe estar por debajo de la entrada")
        if side == "SELL" and not (sl > entry):
            raise ValueError("Para SELL el SL debe estar por encima de la entrada")
        pos = Position(id=self._next_id, side=side, volume=round(volume, 2), entry_price=round(entry, 3),
                       sl=round(sl, 3), tp=round(tp, 3), open_time=time, signal_id=signal_id, score=score,
                       atr=atr, commission=self.costs.commission(volume), best_price=entry, initial_sl=round(sl, 3))
        self._next_id += 1
        self.positions[pos.id] = pos
        self._mark(pos, bid, ask)
        self._log(time, "OPEN", f"ABRIR {side}",
                  f"#{pos.id} {side} {pos.volume:.2f} lotes @ {pos.entry_price:.2f} SL {pos.sl:.2f} TP {pos.tp:.2f}"
                  f" (señal {signal_id or 'manual'}, puntuación {score:.0f})", pos.id)
        return pos

    # ------------------------------------------------------------- valoración
    def _mark(self, pos: Position, bid: float, ask: float) -> None:
        px = self.costs.mark_price(pos.side, bid, ask)
        pos.current_price = px
        pos.gross_pnl = self.costs.pnl(pos.side, pos.entry_price, px, pos.volume)
        pos.mae = min(pos.mae, pos.net_pnl)
        pos.mfe = max(pos.mfe, pos.net_pnl)
        if pos.side == "BUY":
            pos.best_price = max(pos.best_price, px)
        else:
            pos.best_price = min(pos.best_price, px)

    def update_trailing(self, pos: Position, atr: float | None = None) -> bool:
        if not self.rc.trailing_enabled:
            return False
        a = atr if atr and atr > 0 else pos.atr
        if a <= 0:
            return False
        move = (pos.best_price - pos.entry_price) * pos.direction
        if move < self.rc.trailing_activation_atr * a:
            return False
        new_sl = pos.best_price - pos.direction * self.rc.trailing_distance_atr * a
        min_step = max(0.10, 0.15 * a)  # evita micro-ajustes en cada tick
        improved = (new_sl - pos.sl >= min_step) if pos.side == "BUY" else (pos.sl - new_sl >= min_step)
        if improved:
            old = pos.sl
            pos.sl = round(new_sl, 3)
            pos.trailing_active = True
            self._log(self.last_time, "RISK", "TRAILING", f"#{pos.id} SL {old:.2f} → {pos.sl:.2f}", pos.id)
        return improved

    def on_tick(self, bid: float, ask: float, time: datetime) -> list[ClosedTrade]:
        """Revalúa todas las posiciones y ejecuta SL/TP/trailing con precios de mercado."""
        self.last_bid, self.last_ask, self.last_time = bid, ask, time
        closed: list[ClosedTrade] = []
        for pos in list(self.positions.values()):
            self._mark(pos, bid, ask)
            self.update_trailing(pos)
            px = pos.current_price
            if pos.side == "BUY":
                if px <= pos.sl:
                    closed.append(self.close_position(pos.id, bid, ask, time, "TRAILING STOP" if pos.trailing_active else "STOP LOSS"))
                elif pos.tp > 0 and px >= pos.tp:
                    closed.append(self.close_position(pos.id, bid, ask, time, "TAKE PROFIT"))
            else:
                if px >= pos.sl:
                    closed.append(self.close_position(pos.id, bid, ask, time, "TRAILING STOP" if pos.trailing_active else "STOP LOSS"))
                elif pos.tp > 0 and px <= pos.tp:
                    closed.append(self.close_position(pos.id, bid, ask, time, "TAKE PROFIT"))
        return closed

    def on_bar_closed(self) -> None:
        for pos in self.positions.values():
            pos.bars_held += 1

    # ------------------------------------------------------------------ cierre
    def close_position(self, pid: int, bid: float, ask: float, time: datetime, reason: str,
                       exit_override: float | None = None) -> ClosedTrade:
        pos = self.positions.pop(pid)
        exit_px = exit_override if exit_override is not None else self.costs.exit_price(pos.side, bid, ask)
        gross = self.costs.pnl(pos.side, pos.entry_price, exit_px, pos.volume)
        net = gross - pos.commission
        self.balance += net
        trade = ClosedTrade(id=pos.id, side=pos.side, volume=pos.volume, entry_price=pos.entry_price,
                            exit_price=round(exit_px, 3), open_time=pos.open_time, close_time=time,
                            gross_pnl=round(gross, 2), commission=round(pos.commission, 2), net_pnl=round(net, 2),
                            reason=reason, score=pos.score, signal_id=pos.signal_id, sl=pos.initial_sl, tp=pos.tp,
                            mae=round(min(pos.mae, net), 2), mfe=round(max(pos.mfe, net), 2))
        self.closed.append(trade)
        self._log(time, "CLOSE", f"CERRAR #{pid}",
                  f"#{pid} {pos.side} cerrada @ {exit_px:.2f} · motivo: {reason} · neto {net:+.2f} USD "
                  f"(bruto {gross:+.2f}, comisión {pos.commission:.2f})", pid, net=net)
        return trade

    def close_many(self, ids: Iterable[int], time: datetime, reason: str) -> list[ClosedTrade]:
        ids = [pid for pid in ids if pid in self.positions]
        if ids and (self.last_bid <= 0 or self.last_ask <= 0):
            raise ValueError("Sin cotización válida: no se puede valorar el cierre")
        out = []
        for pid in ids:
            if pid in self.positions:
                out.append(self.close_position(pid, self.last_bid, self.last_ask, time, reason))
        return out

    def close_all(self, time: datetime, reason: str) -> list[ClosedTrade]:
        return self.close_many(list(self.positions), time, reason)

    def close_positive(self, time: datetime, reason: str = "CIERRE POSITIVAS") -> list[ClosedTrade]:
        return self.close_many([p.id for p in self.positions.values() if p.net_pnl > 0], time, reason)

    def close_negative(self, time: datetime, reason: str = "CIERRE NEGATIVAS") -> list[ClosedTrade]:
        return self.close_many([p.id for p in self.positions.values() if p.net_pnl <= 0], time, reason)

    def reset(self, initial_balance: float | None = None) -> None:
        if initial_balance is not None:
            self.initial_balance = float(initial_balance)
        self.balance = self.initial_balance
        self.positions.clear()
        self.closed.clear()
        self._next_id = 1
