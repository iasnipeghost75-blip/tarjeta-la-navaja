"""B. LIVE TRADING SIMULATOR — gráfico XAUUSD, señales y posiciones simuladas."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QVBoxLayout,
                               QWidget)

from ...analysis import indicators as ind
from ...analysis.structure import support_resistance_levels
from ...config import VALID_TIMEFRAMES
from ...core import TradingController
from .. import theme as T
from ..widgets import CandleChart, ChartMarker, ChartPosition, Panel
from .common import fill_table, make_table, money

SPEEDS = {"x1": 1, "x5": 5, "x20": 20, "x60": 60}


class LivePage(QWidget):
    speed_changed = Signal(int)

    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        root = QVBoxLayout(self)
        root.setSpacing(10)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Temporalidad:"))
        self.tf = QComboBox()
        self.tf.addItems(list(VALID_TIMEFRAMES))
        self.tf.setCurrentText(ctrl.tf)
        self.tf.currentTextChanged.connect(lambda _t: self.refresh())
        bar.addWidget(self.tf)
        bar.addWidget(QLabel("Velocidad de simulación:"))
        self.speed = QComboBox()
        self.speed.addItems(list(SPEEDS))
        self.speed.currentTextChanged.connect(lambda t: self.speed_changed.emit(SPEEDS[t]))
        bar.addWidget(self.speed)
        self.quote = QLabel("—")
        self.quote.setStyleSheet(f"color:{T.GOLD}; font-size:15px; font-weight:bold;")
        bar.addStretch(1)
        bar.addWidget(self.quote)
        root.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        chart_panel = Panel()
        self.chart = CandleChart()
        chart_panel.v.addWidget(self.chart)
        split.addWidget(chart_panel)

        bottom = QSplitter(Qt.Horizontal)
        pos_panel = Panel("Posiciones simuladas")
        self.positions = make_table(["ID", "Tipo", "Lotes", "Entrada", "Actual", "SL", "TP", "Trailing",
                                     "Velas", "Beneficio neto $"])
        self.positions.itemSelectionChanged.connect(self._sel_changed)
        pos_panel.v.addWidget(self.positions, 1)
        btns = QHBoxLayout()
        self.b_buy = QPushButton("▲ COMPRA SIM.")
        self.b_buy.setObjectName("buy")
        self.b_sell = QPushButton("▼ VENTA SIM.")
        self.b_sell.setObjectName("sell")
        self.b_close = QPushButton("Cerrar seleccionada")
        self.b_close_pos = QPushButton("Cerrar positivas")
        self.b_close_neg = QPushButton("Cerrar negativas")
        self.b_close_all = QPushButton("Cerrar TODAS")
        self.b_close_all.setObjectName("warn")
        self.b_buy.clicked.connect(lambda: self._manual("BUY"))
        self.b_sell.clicked.connect(lambda: self._manual("SELL"))
        self.b_close.clicked.connect(self._close_selected)
        self.b_close_pos.clicked.connect(lambda: (self.ctrl.close_positive(), self.refresh()))
        self.b_close_neg.clicked.connect(lambda: (self.ctrl.close_negative(), self.refresh()))
        self.b_close_all.clicked.connect(lambda: (self.ctrl.close_all(), self.refresh()))
        for b in (self.b_buy, self.b_sell, self.b_close, self.b_close_pos, self.b_close_neg, self.b_close_all):
            btns.addWidget(b)
        pos_panel.v.addLayout(btns)
        self.totals = QLabel("—")
        pos_panel.v.addWidget(self.totals)
        self.b_close.setEnabled(False)
        bottom.addWidget(pos_panel)

        sig_panel = Panel("Señales detectadas")
        self.signals = make_table(["Hora", "Tipo", "Precio", "Punt.", "Factores", "Estado / motivo"])
        self.signals.itemSelectionChanged.connect(self._show_signal)
        sig_panel.v.addWidget(self.signals, 1)
        self.sig_detail = QLabel("Seleccione una señal para ver su explicación.")
        self.sig_detail.setWordWrap(True)
        self.sig_detail.setObjectName("subtitle")
        sig_panel.v.addWidget(self.sig_detail)
        bottom.addWidget(sig_panel)
        bottom.setSizes([620, 480])
        split.addWidget(bottom)
        split.setSizes([430, 300])
        root.addWidget(split, 1)
        self._pos_ids: list[int] = []

    # ---------------------------------------------------------------- acciones
    def _manual(self, side: str) -> None:
        ok, msg = self.ctrl.manual_open(side)
        if not ok:
            QMessageBox.information(self, "Operación rechazada por el gestor de riesgo", msg)
        self.refresh()

    def _sel_changed(self) -> None:
        self.b_close.setEnabled(bool(self.positions.selectedItems()))

    def selected_position_id(self) -> int | None:
        rows = {i.row() for i in self.positions.selectedItems()}
        if not rows:
            return None
        row = min(rows)
        return self._pos_ids[row] if row < len(self._pos_ids) else None

    def _close_selected(self) -> None:
        pid = self.selected_position_id()
        if pid is not None:
            self.ctrl.close_position(pid)
            self.positions.clearSelection()
        self.refresh()

    def _show_signal(self) -> None:
        rows = {i.row() for i in self.signals.selectedItems()}
        recs = list(self.ctrl.signals)
        if rows and min(rows) < len(recs):
            r = recs[min(rows)]
            hist = (r.signal.historical or {}).get("text", "")
            self.sig_detail.setText(f"{r.signal.explanation}\n{hist}\nDecisión: "
                                    f"{'ACEPTADA' if r.accepted else 'RECHAZADA'} — {r.reason}")

    # ---------------------------------------------------------------- refresco
    def refresh(self) -> None:
        c = self.ctrl
        s = c.snapshot()
        if s["bid"] is not None:
            self.quote.setText(f"XAUUSD  BID {s['bid']:.2f}   ASK {s['ask']:.2f}   SPREAD {s['spread']:.2f}")
        tf = self.tf.currentText()
        try:
            df = c.candles(tf, 300, include_forming=True)
        except Exception as exc:  # noqa: BLE001 - se informa en la UI
            self.quote.setText(f"Error de datos: {exc}")
            return
        icfg = c.cfg.indicators
        close = df["close"]
        overlays = {"ema_fast": ind.ema(close, icfg.ema_fast), "ema_mid": ind.ema(close, icfg.ema_mid)}
        if len(df) >= icfg.ema_slow:
            overlays["ema_slow"] = ind.ema(close, icfg.ema_slow)
        if c.analysis and tf == c.tf:
            levels = [(lv.price, lv.kind) for lv in c.analysis.levels]
        else:
            levels = [(lv.price, lv.kind) for lv in support_resistance_levels(df.iloc[:-1], icfg.swing_lookback, icfg.sr_levels)]
        markers = [ChartMarker(r.signal.time, r.signal.price, r.signal.side, r.accepted)
                   for r in c.signals if r.signal.timeframe == tf]
        positions = [ChartPosition(p.id, p.side, p.entry_price, p.sl, p.tp, p.net_pnl) for p in c.sim.positions.values()]
        self.chart.set_data(df, overlays, levels, markers, positions, s["bid"], s["ask"], f"XAUUSD {tf}")

        pos = sorted(c.sim.positions.values(), key=lambda p: p.id)
        sel = self.selected_position_id()
        self._pos_ids = [p.id for p in pos]
        rows, colors = [], []
        for p in pos:
            rows.append([p.id, p.side, f"{p.volume:.2f}", f"{p.entry_price:.2f}", f"{p.current_price:.2f}",
                         f"{p.sl:.2f}", f"{p.tp:.2f}", "sí" if p.trailing_active else "no", p.bars_held,
                         money(p.net_pnl, True)])
            colors.append({1: T.GREEN if p.side == "BUY" else T.RED, 9: T.pnl_color(p.net_pnl)})
        fill_table(self.positions, rows, colors)
        if sel in self._pos_ids:
            self.positions.selectRow(self._pos_ids.index(sel))
        pos_sum = sum(p.net_pnl for p in pos if p.net_pnl > 0)
        neg_sum = sum(p.net_pnl for p in pos if p.net_pnl <= 0)
        self.totals.setText(f"Posiciones: {len(pos)} · Positivas {money(pos_sum, True)} $ · Negativas "
                            f"{money(neg_sum, True)} $ · NETO ACUMULADO {money(s['floating'], True)} $ · "
                            f"Realizado sesión {money(s['realized'], True)} $")
        self.totals.setStyleSheet(f"color:{T.pnl_color(s['floating'])}; font-weight:bold;")
        sig_rows, sig_colors = [], []
        for r in list(c.signals)[:100]:
            sg = r.signal
            sig_rows.append([sg.time.strftime("%m-%d %H:%M"), sg.side, f"{sg.price:.2f}", f"{sg.score:.0f}",
                             f"{sg.confluence}", ("✔ " if r.accepted else "✖ ") + r.reason])
            sig_colors.append({1: T.GREEN if sg.side == "BUY" else T.RED, 5: T.GREEN if r.accepted else T.AMBER})
        fill_table(self.signals, sig_rows, sig_colors)
        blocked = s["blocked"]
        self.b_buy.setEnabled(not blocked)
        self.b_sell.setEnabled(not blocked)
