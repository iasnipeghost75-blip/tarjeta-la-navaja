"""Controlador central de JARVIS (independiente de la interfaz gráfica).

Ciclo por tick (``step``):
1. Lee el tick de la fuente (sintética, CSV o MT5 DEMO) y lo valida.
   Errores de datos -> PAUSA automática (se reanuda manualmente).
2. Revalúa posiciones (SL/TP/trailing) con Bid/Ask.
3. Al cerrarse una vela de la temporalidad de análisis: análisis completo,
   protección de volatilidad, cierre inteligente y, si procede, apertura
   simulada filtrada por el gestor de riesgo.
4. Actualiza límites de riesgo (pérdida diaria, drawdown) y guarda todo en SQLite.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import pandas as pd

from ..analysis import AnalysisEngine, ConfidenceCalibrator, MarketAnalysis, Signal, quick_trend
from ..config import AppConfig, resolve_path
from ..data import DataError, MarketDataProvider, SyntheticGoldProvider, Tick, create_provider
from ..data.validation import validate_candles, validate_tick
from ..safety import TradingMode
from ..storage import Database
from ..trading import CostModel, MultiPositionSimulator, RiskManager, SmartCloseManager
from ..trading.models import ClosedTrade, Decision

DATA_ERROR_MARKERS = ("NaN", "no numérico", "<= 0", "Ask < Bid", "anterior", "No se recibió", "Velas")


@dataclass
class SignalRecord:
    signal: Signal
    accepted: bool
    reason: str


class TradingController:
    def __init__(self, config: AppConfig, provider: MarketDataProvider | None = None,
                 db: Database | None = None) -> None:
        config.validate()
        self.cfg = copy.deepcopy(config)
        self.mode = self.cfg.trading_mode  # SIMULATION o DEMO, nunca LIVE
        self.provider = provider or create_provider(self.cfg)
        self.db = db or Database(resolve_path(self.cfg.database_path))
        self.costs = CostModel.from_config(self.cfg.costs)
        self.decisions: deque[Decision] = deque(maxlen=800)
        self.sim = MultiPositionSimulator(self.cfg.risk.initial_balance, self.costs, self.cfg.risk,
                                          on_decision=self._on_decision)
        self.risk = RiskManager(self.cfg.risk, self.cfg.strategy, self.cfg.costs.contract_size)
        self.smart = SmartCloseManager(self.cfg.smart_close)
        self.engine = AnalysisEngine(self.cfg.indicators, self.cfg.strategy, use_volume=self.cfg.indicators.use_volume)
        cal = self.db.get_kv("calibration")
        self.calibrator = ConfidenceCalibrator.from_dict(cal) if cal else ConfidenceCalibrator(
            min_trades=self.cfg.backtest.min_trades_for_stats)
        self.session_id: Optional[int] = None
        self.last_tick: Optional[Tick] = None
        self.analysis: Optional[MarketAnalysis] = None
        self.signals: deque[SignalRecord] = deque(maxlen=200)
        self.auto_trading = True
        self.running = False
        self.started = False
        self.tick_count = 0
        self.bar_index = 0
        self._last_bar_time: Optional[pd.Timestamp] = None
        self._last_jump = 0.0
        self.last_error = ""
        self.listeners: list[Callable[[str], None]] = []

    # --------------------------------------------------------------- utilidades
    def _on_decision(self, d: Decision) -> None:
        if d.time is None:
            d.time = self.now
        self.decisions.appendleft(d)
        if self.session_id is not None:
            self.db.save_decision(self.session_id, d)

    def log(self, category: str, action: str, detail: str, pid: int | None = None) -> None:
        self._on_decision(Decision(self.now, category, action, detail, pid))

    @property
    def now(self) -> datetime:
        if self.last_tick is not None:
            return self.last_tick.time
        return datetime.now()

    @property
    def tf(self) -> str:
        return self.cfg.market.analysis_timeframe

    @property
    def is_synthetic(self) -> bool:
        return self.provider.is_synthetic

    # ------------------------------------------------------------------ inicio
    def start(self) -> None:
        if self.started:
            return
        self.provider.connect()
        self.session_id = self.db.start_session(self.mode.value, self.provider.describe(), self.sim.initial_balance)
        self.started = True
        self.running = True
        tick = self.provider.step()
        self.last_tick = tick
        self.sim.on_tick(tick.bid, tick.ask, tick.time)
        self.risk.start(self.sim.equity, tick.time)
        self.log("SYSTEM", "INICIO", f"Sesión #{self.session_id} en modo {self.mode.value} · fuente "
                 f"{self.provider.describe()} · ejecución 100 % simulada")
        self._analyze_if_new_bar(force=True)

    def stop(self) -> None:
        self.running = False
        self.provider.disconnect()
        self.started = False

    # -------------------------------------------------------------------- ciclo
    def step(self) -> list[ClosedTrade]:
        if not self.started:
            self.start()
        if not self.running:
            return []
        closed: list[ClosedTrade] = []
        try:
            tick = self.provider.step()
        except DataError as exc:
            self._data_pause(str(exc))
            return []
        prev = self.last_tick
        issues = validate_tick(tick, prev, max_spread=self.cfg.risk.max_spread_usd * 5,
                               max_jump=self.cfg.risk.max_tick_jump_usd)
        data_errors = [i for i in issues if any(m in i for m in DATA_ERROR_MARKERS)]
        if data_errors:
            self._data_pause("; ".join(data_errors))
            return []
        if self.risk.state.data_paused:
            # datos de nuevo válidos, pero la reanudación es manual por seguridad
            self.last_tick = tick
            closed = self.sim.on_tick(tick.bid, tick.ask, tick.time)  # SL/TP siguen protegiendo
            for t in closed:
                self.db.save_trade(self.session_id, t)
            return closed
        self._last_jump = abs(tick.mid - prev.mid) if prev else 0.0
        if issues:  # salto/spread anómalo: protección de volatilidad
            self.log("RISK", "VOLATILIDAD", "Tick anómalo: " + "; ".join(issues) + " → entradas bloqueadas")
        self.last_tick = tick
        self.tick_count += 1
        closed += self.sim.on_tick(tick.bid, tick.ask, tick.time)
        self.risk.set_volatility(self.analysis.atr_ratio if self.analysis else None, self._last_jump)
        try:
            closed += self._analyze_if_new_bar()
        except DataError as exc:
            self._data_pause(str(exc))
        closed += self._apply_risk_limits()
        closed += self.smart.evaluate(self.sim, tick.time)
        for t in closed:
            self.db.save_trade(self.session_id, t)
        if self.tick_count % 10 == 0:
            self.db.save_equity(self.session_id, tick.time, self.sim.balance, self.sim.equity, len(self.sim.positions))
        return closed

    def _apply_risk_limits(self) -> list[ClosedTrade]:
        events = self.risk.update(self.sim.equity, self.now)
        out: list[ClosedTrade] = []
        for e in events:
            self.log("RISK", "LÍMITE", e)
        if events and (self.risk.state.daily_limit_hit or self.risk.state.drawdown_limit_hit) and self.sim.positions:
            out = self.sim.close_all(self.now, "LÍMITE DE RIESGO")
        return out

    def _data_pause(self, reason: str) -> None:
        if not self.risk.state.data_paused:
            self.risk.pause_for_data(reason)
            self.last_error = reason
            self.log("SYSTEM", "PAUSA AUTOMÁTICA", f"Error de datos: {reason}. Entradas suspendidas hasta reanudar.")

    def _analyze_if_new_bar(self, force: bool = False) -> list[ClosedTrade]:
        candles = self.provider.get_candles(self.tf, self.cfg.market.history_bars)
        if candles.empty:
            raise DataError("Sin velas cerradas")
        last_time = pd.Timestamp(candles["time"].iloc[-1])
        if not force and self._last_bar_time is not None and last_time == self._last_bar_time:
            return []
        issues = validate_candles(candles, min_rows=self.engine.min_bars)
        if issues:
            raise DataError("Velas inválidas: " + "; ".join(issues))
        new_bar = self._last_bar_time is not None
        self._last_bar_time = last_time
        self.bar_index += 1
        if new_bar:
            self.sim.on_bar_closed()
        a = self.engine.analyze(candles, self.tf)
        self.analysis = a
        self.risk.set_volatility(a.atr_ratio, self._last_jump)
        for p in self.sim.positions.values():  # trailing con el ATR actual
            self.sim.update_trailing(p, a.atr)
        closed: list[ClosedTrade] = []
        if a.signal is not None:
            a.signal.historical = self.calibrator.estimate(a.signal.score)
            closed += self.smart.evaluate(self.sim, self.now, opposite_signal_side=a.signal.side)
            self._handle_signal(a.signal, a.atr)
        return closed

    def _handle_signal(self, sig: Signal, atr: float) -> None:
        tick = self.last_tick
        if not self.auto_trading:
            accepted, reason = False, "Auto-trading desactivado (solo análisis)"
        else:
            chk = self.risk.check_entry(sig.side, self.sim, sig.id, tick.mid, atr, tick.spread, self.bar_index)
            accepted, reason = chk.allowed, chk.reason
            if chk.allowed:
                self._open(sig.side, chk.volume, atr, sig.id, sig.score)
                self.risk.register_entry(sig.side, sig.id, self.bar_index)
        self.signals.appendleft(SignalRecord(sig, accepted, reason))
        self.db.save_signal(self.session_id, sig, accepted, reason)
        self.log("SIGNAL", f"SEÑAL {sig.side}", f"{'ACEPTADA' if accepted else 'RECHAZADA'} ({reason}) · {sig.explanation}")

    def _open(self, side: str, volume: float, atr: float, signal_id: str, score: float):
        tick = self.last_tick
        sl_d, tp_d = self.risk.stop_distances(atr)
        entry = self.costs.entry_price(side, tick.bid, tick.ask)
        d = 1 if side == "BUY" else -1
        return self.sim.open_position(side, volume, entry - d * sl_d, entry + d * tp_d, tick.bid, tick.ask,
                                      tick.time, signal_id, score, atr, entry_override=entry)

    # --------------------------------------------------------- acciones de UI
    def manual_open(self, side: str) -> tuple[bool, str]:
        """Apertura manual simulada, sometida a las MISMAS reglas de riesgo."""
        if not self.started or self.last_tick is None or self.analysis is None:
            return False, "Sistema no iniciado"
        sig_id = f"MANUAL-{side}-{self.now.isoformat()}"
        tick = self.last_tick
        chk = self.risk.check_entry(side, self.sim, sig_id, tick.mid, self.analysis.atr, tick.spread, None)
        if not chk.allowed:
            self.log("RISK", "MANUAL RECHAZADA", f"{side}: {chk.reason}")
            return False, chk.reason
        self._open(side, chk.volume, self.analysis.atr, sig_id, 0.0)
        self.risk.register_entry(side, sig_id, None)
        return True, f"Posición {side} simulada abierta ({chk.volume:.2f} lotes)"

    def close_position(self, pid: int) -> Optional[ClosedTrade]:
        if pid not in self.sim.positions:
            return None
        t = self.sim.close_many([pid], self.now, "CIERRE MANUAL")[0]
        self.db.save_trade(self.session_id, t)
        return t

    def _bulk(self, trades: list[ClosedTrade]) -> list[ClosedTrade]:
        for t in trades:
            self.db.save_trade(self.session_id, t)
        return trades

    def close_all(self, reason: str = "CIERRE MANUAL DE GRUPO") -> list[ClosedTrade]:
        return self._bulk(self.sim.close_all(self.now, reason))

    def close_positive(self) -> list[ClosedTrade]:
        return self._bulk(self.sim.close_positive(self.now))

    def close_negative(self) -> list[ClosedTrade]:
        return self._bulk(self.sim.close_negative(self.now))

    def emergency_stop(self) -> list[ClosedTrade]:
        self.risk.emergency()
        self.auto_trading = False
        closed = self.close_all("PARADA DE EMERGENCIA")
        self.log("SYSTEM", "EMERGENCIA", f"Parada de emergencia: {len(closed)} posiciones cerradas, "
                 "auto-trading desactivado, nuevas entradas bloqueadas.")
        return closed

    def reset_emergency(self) -> None:
        self.risk.reset_emergency()
        self.log("SYSTEM", "REARME", "Parada de emergencia rearmada (auto-trading sigue desactivado hasta activarlo)")

    def resume_after_data_pause(self) -> bool:
        if not self.risk.state.data_paused:
            return False
        try:
            candles = self.provider.get_candles(self.tf, self.cfg.market.history_bars)
            tick = self.provider.step()
        except DataError as exc:
            self.log("SYSTEM", "REANUDAR FALLIDO", str(exc))
            return False
        issues = validate_candles(candles, self.engine.min_bars) + \
            [i for i in validate_tick(tick, None, self.cfg.risk.max_spread_usd * 5, 1e9)]
        if issues:
            self.log("SYSTEM", "REANUDAR FALLIDO", "; ".join(issues))
            return False
        self.last_tick = tick
        self.risk.resume_data()
        self.last_error = ""
        self.log("SYSTEM", "REANUDADO", "Datos válidos de nuevo: sistema reanudado")
        return True

    def set_auto_trading(self, enabled: bool) -> None:
        self.auto_trading = bool(enabled)
        self.log("SYSTEM", "AUTO-TRADING", "Activado" if enabled else "Desactivado")

    def set_running(self, running: bool) -> None:
        self.running = bool(running)
        self.log("SYSTEM", "SIMULACIÓN", "En marcha" if running else "En pausa")

    def reset_account(self) -> None:
        self.close_all("REINICIO DE CUENTA")
        self.sim.reset(self.cfg.risk.initial_balance)
        self.risk.reset_limits(self.sim.equity, self.now)
        self.session_id = self.db.start_session(self.mode.value, self.provider.describe(), self.sim.initial_balance,
                                                "reinicio")
        self.signals.clear()
        self.log("SYSTEM", "REINICIO", f"Cuenta DEMO reiniciada con {self.sim.initial_balance:,.2f} USD")

    def inject_volatility_spike(self, usd: float = 25.0) -> bool:
        if isinstance(self.provider, SyntheticGoldProvider):
            self.provider.inject_volatility_spike(usd)
            self.log("SYSTEM", "PRUEBA", f"Evento de volatilidad simulado (+{usd:.0f} USD) en el próximo tick")
            return True
        return False

    def inject_data_error(self) -> bool:
        if isinstance(self.provider, SyntheticGoldProvider):
            self.provider.inject_data_error()
            self.log("SYSTEM", "PRUEBA", "Error de datos simulado en el próximo tick")
            return True
        return False

    def apply_config(self, cfg: AppConfig) -> list[str]:
        """Aplica una nueva configuración en caliente. Devuelve avisos (p.ej. requiere reinicio)."""
        cfg.validate()
        warnings = []
        if (cfg.market.data_source != self.cfg.market.data_source or cfg.market.csv_path != self.cfg.market.csv_path
                or cfg.market.synthetic_seed != self.cfg.market.synthetic_seed or cfg.mode != self.cfg.mode):
            warnings.append("El cambio de modo/fuente de datos se aplicará al reiniciar la aplicación.")
        new_mode = cfg.mode
        if cfg.risk.initial_balance != self.cfg.risk.initial_balance:
            warnings.append("El nuevo capital inicial se aplica al pulsar 'Reiniciar cuenta DEMO'.")
        keep_market = self.cfg.market
        self.cfg = copy.deepcopy(cfg)
        self.cfg.market.data_source = keep_market.data_source
        self.cfg.market.csv_path = keep_market.csv_path
        self.cfg.mode = self.mode.value  # el modo en ejecución no cambia en caliente
        self._pending_mode = new_mode
        self.sim.rc = self.cfg.risk
        self.costs = CostModel.from_config(self.cfg.costs)
        self.sim.costs = self.costs
        self.risk.cfg = self.cfg.risk
        self.risk.strat = self.cfg.strategy
        self.smart.cfg = self.cfg.smart_close
        self.engine = AnalysisEngine(self.cfg.indicators, self.cfg.strategy, use_volume=self.cfg.indicators.use_volume)
        self._last_bar_time = None
        if self.started:
            try:
                self._analyze_if_new_bar(force=True)
            except DataError as exc:
                self._data_pause(str(exc))
        self.log("SYSTEM", "CONFIGURACIÓN", "Configuración aplicada")
        return warnings

    def set_calibrator(self, cal: ConfidenceCalibrator) -> None:
        self.calibrator = cal
        self.db.set_kv("calibration", cal.to_dict())

    # ---------------------------------------------------------------- consultas
    def candles(self, timeframe: str, count: int, include_forming: bool = True) -> pd.DataFrame:
        return self.provider.get_candles(timeframe, count, include_forming=include_forming)

    def historical_candles(self, timeframe: str, bars: int, seed: int | None = None) -> tuple[pd.DataFrame, str]:
        """Datos históricos para backtesting según la fuente configurada."""
        src = self.cfg.market.data_source
        if src == "synthetic" or isinstance(self.provider, SyntheticGoldProvider):
            from ..data import generate_synthetic_candles
            s = self.cfg.backtest.seed if seed is None else seed
            return (generate_synthetic_candles(bars, timeframe, seed=s, start_price=self.cfg.market.synthetic_start_price),
                    f"SINTÉTICOS (semilla {s}) — no representan el mercado real")
        if src == "csv":
            from ..data import load_candles_csv, resample_candles
            df = load_candles_csv(resolve_path(self.cfg.market.csv_path))
            return resample_candles(df, timeframe).tail(bars).reset_index(drop=True), f"CSV {self.cfg.market.csv_path}"
        return self.provider.get_candles(timeframe, bars), f"MT5 DEMO {self.provider.describe()}"

    def multi_timeframe_trends(self) -> dict[str, str]:
        out = {}
        for tf in self.cfg.market.timeframes:
            try:
                out[tf] = quick_trend(self.provider.get_candles(tf, 260))
            except DataError:
                out[tf] = "sin datos"
        return out

    def historical_stats(self) -> dict:
        df = self.db.trades()
        n = len(df)
        wins = int((df["net_pnl"] > 0).sum()) if n else 0
        return {"trades": n, "wins": wins, "win_rate": wins / n if n else None,
                "net": float(df["net_pnl"].sum()) if n else 0.0}

    def snapshot(self) -> dict:
        sim, rs = self.sim, self.risk.state
        session_trades = sim.closed
        wins = sum(1 for t in session_trades if t.net_pnl > 0)
        return {
            "mode": self.mode.value,
            "source": self.provider.describe(),
            "synthetic": self.is_synthetic,
            "time": self.now,
            "bid": self.last_tick.bid if self.last_tick else None,
            "ask": self.last_tick.ask if self.last_tick else None,
            "spread": self.last_tick.spread if self.last_tick else None,
            "balance": sim.balance,
            "equity": sim.equity,
            "floating": sim.floating_pnl,
            "realized": sim.balance - sim.initial_balance,
            "initial_balance": sim.initial_balance,
            "open_positions": len(sim.positions),
            "total_lots": sim.total_lots,
            "session_trades": len(session_trades),
            "session_win_rate": wins / len(session_trades) if session_trades else None,
            "daily_loss": self.risk.daily_loss(sim.equity),
            "daily_limit": rs.day_start_equity * self.cfg.risk.daily_loss_limit_pct / 100,
            "status": self.risk.status_text() if self.running else "SIMULACIÓN EN PAUSA",
            "blocked": self.risk.trading_blocked,
            "emergency": rs.emergency_stop,
            "data_paused": rs.data_paused,
            "volatility_block": rs.volatility_block,
            "auto_trading": self.auto_trading,
            "running": self.running,
            "ticks": self.tick_count,
        }
