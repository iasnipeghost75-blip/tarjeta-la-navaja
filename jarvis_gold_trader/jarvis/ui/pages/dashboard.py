"""A. DASHBOARD — estado global de la cuenta DEMO simulada y del sistema."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from ...core import TradingController
from .. import theme as T
from ..widgets import ArcReactor, LineChart, Panel, StatCard, StatusLed
from .common import money


class DashboardPage(QWidget):
    emergency_requested = Signal()

    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        self.equity_hist: deque[float] = deque(maxlen=600)
        root = QVBoxLayout(self)
        root.setSpacing(12)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.c_balance = StatCard("Balance DEMO", subtitle="Capital simulado realizado")
        self.c_equity = StatCard("Equity", subtitle="Balance + flotante neto")
        self.c_pnl = StatCard("Beneficio / Pérdida", subtitle="Realizado + flotante (neto de costes)")
        self.c_open = StatCard("Operaciones abiertas", subtitle="Lotes totales")
        self.c_wr = StatCard("Tasa de acierto histórica", subtitle="Todas las sesiones simuladas (SQLite)")
        self.c_status = StatCard("Estado del sistema", color=T.GREEN)
        for i, c in enumerate([self.c_balance, self.c_equity, self.c_pnl, self.c_open, self.c_wr, self.c_status]):
            cards.addWidget(c, i // 3, i % 3)
        root.addLayout(cards)

        mid = QHBoxLayout()
        mid.setSpacing(12)
        core = Panel("Núcleo de inteligencia")
        self.reactor = ArcReactor()
        core.v.addWidget(self.reactor, 1)
        self.ai_text = QLabel("—")
        self.ai_text.setWordWrap(True)
        self.ai_text.setObjectName("subtitle")
        core.v.addWidget(self.ai_text)
        mid.addWidget(core, 2)

        eqp = Panel("Curva de equity (sesión)")
        self.eq_chart = LineChart(title="USD")
        eqp.v.addWidget(self.eq_chart, 1)
        ctrl_row = QHBoxLayout()
        self.led = StatusLed(T.GREEN)
        self.led_lbl = QLabel("OPERATIVO")
        ctrl_row.addWidget(self.led)
        ctrl_row.addWidget(self.led_lbl, 1)
        self.btn_run = QPushButton("⏸ PAUSAR SIMULACIÓN")
        self.btn_run.clicked.connect(self._toggle_run)
        self.btn_auto = QPushButton("AUTO-TRADING: ON")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setChecked(True)
        self.btn_auto.clicked.connect(self._toggle_auto)
        self.btn_emerg = QPushButton("⛔ PARADA DE EMERGENCIA")
        self.btn_emerg.setObjectName("danger")
        self.btn_emerg.clicked.connect(self.emergency_requested.emit)
        self.btn_rearm = QPushButton("REARMAR")
        self.btn_rearm.setObjectName("warn")
        self.btn_rearm.clicked.connect(self._rearm)
        self.btn_resume = QPushButton("REANUDAR TRAS ERROR DE DATOS")
        self.btn_resume.setObjectName("warn")
        self.btn_resume.clicked.connect(self._resume)
        for b in (self.btn_run, self.btn_auto, self.btn_rearm, self.btn_resume, self.btn_emerg):
            ctrl_row.addWidget(b)
        eqp.v.addLayout(ctrl_row)
        mid.addWidget(eqp, 3)
        root.addLayout(mid, 1)

        feed = Panel("Registro de decisiones en tiempo real")
        self.feed = QListWidget()
        self.feed.setMaximumHeight(170)
        feed.v.addWidget(self.feed)
        root.addWidget(feed)
        self._last_feed_id = None

    # ----------------------------------------------------------------- acciones
    def _toggle_run(self) -> None:
        self.ctrl.set_running(not self.ctrl.running)
        self.refresh()

    def _toggle_auto(self) -> None:
        if self.ctrl.risk.state.emergency_stop and self.btn_auto.isChecked():
            self.btn_auto.setChecked(False)
            return
        self.ctrl.set_auto_trading(self.btn_auto.isChecked())
        self.refresh()

    def _rearm(self) -> None:
        self.ctrl.reset_emergency()
        self.refresh()

    def _resume(self) -> None:
        self.ctrl.resume_after_data_pause()
        self.refresh()

    # ------------------------------------------------------------------ refresco
    def record_equity(self) -> None:
        self.equity_hist.append(self.ctrl.sim.equity)

    def refresh(self) -> None:
        s = self.ctrl.snapshot()
        self.c_balance.set(f"{money(s['balance'])} $", f"Inicial {money(s['initial_balance'])} $ · simulado")
        self.c_equity.set(f"{money(s['equity'])} $", f"Flotante {money(s['floating'], True)} $",
                          T.pnl_color(s["equity"] - s["initial_balance"]))
        total = s["equity"] - s["initial_balance"]
        self.c_pnl.set(f"{money(total, True)} $", f"Realizado {money(s['realized'], True)} · pérdida diaria "
                       f"{money(s['daily_loss'])}/{money(s['daily_limit'])}", T.pnl_color(total))
        self.c_open.set(f"{s['open_positions']}", f"{s['total_lots']:.2f} lotes / máx "
                        f"{self.ctrl.cfg.risk.max_total_lots:.2f} · máx {self.ctrl.cfg.risk.max_positions} posiciones")
        hs = self.ctrl.historical_stats()
        if hs["win_rate"] is None:
            self.c_wr.set("—", "Sin operaciones cerradas todavía")
        else:
            sess = s["session_win_rate"]
            self.c_wr.set(f"{hs['win_rate']:.1%}", f"{hs['wins']}/{hs['trades']} ganadoras · sesión "
                          f"{'—' if sess is None else f'{sess:.0%}'}")
        status = s["status"]
        color = T.RED if s["emergency"] or s["data_paused"] or s["blocked"] else T.AMBER if (
            s["volatility_block"] or not s["running"]) else T.GREEN
        self.c_status.set(status if len(status) < 22 else status[:21] + "…",
                          f"{s['mode']} · {s['source']} · auto {'ON' if s['auto_trading'] else 'OFF'}", color)
        self.c_status.setToolTip(status)
        self.led.set_color(color, blink=color != T.GREEN)
        self.led_lbl.setText(status)
        self.btn_run.setText("⏸ PAUSAR SIMULACIÓN" if s["running"] else "▶ REANUDAR SIMULACIÓN")
        self.btn_auto.setChecked(s["auto_trading"])
        self.btn_auto.setText(f"AUTO-TRADING: {'ON' if s['auto_trading'] else 'OFF'}")
        self.btn_rearm.setEnabled(s["emergency"])
        self.btn_resume.setEnabled(s["data_paused"])
        a = self.ctrl.analysis
        if a:
            best = max(a.long_eval, a.short_eval, key=lambda e: e.score)
            line1 = f"{a.trend.upper()}"
            line2 = f"{best.side} {best.score:.0f}/100"
            self.reactor.set_state(color, line1, line2, best.score, active=s["running"])
            self.ai_text.setText(" · ".join(a.summary_lines()[:2]) + "\n" + (a.notes[0] if a.notes else
                                 (a.signal.explanation[:220] if a.signal else "")))
        self.eq_chart.baseline = s["initial_balance"]
        self.eq_chart.set_series(list(self.equity_hist), T.pnl_color(total) if total else T.CYAN)
        self._refresh_feed()

    def _refresh_feed(self) -> None:
        decs = list(self.ctrl.decisions)[:60]
        head = id(decs[0]) if decs else None
        if head == self._last_feed_id:
            return
        self._last_feed_id = head
        self.feed.clear()
        for d in decs:
            t = d.time.strftime("%H:%M:%S") if hasattr(d.time, "strftime") else str(d.time)
            self.feed.addItem(f"[{t}] {d.category:<11} {d.action:<18} {d.detail[:160]}")
