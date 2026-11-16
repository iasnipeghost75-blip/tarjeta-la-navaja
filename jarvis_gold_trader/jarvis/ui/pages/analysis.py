"""C. AI MARKET ANALYSIS — tendencia, técnico, volatilidad, probabilidad histórica y explicación."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ...core import TradingController
from .. import theme as T
from ..widgets import GaugeBar, Panel
from .common import fill_table, make_table


class AnalysisPage(QWidget):
    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        root = QGridLayout(self)
        root.setSpacing(12)

        # Tendencia
        tp = Panel("Tendencia actual")
        self.trend = QLabel("—")
        self.trend.setStyleSheet("font-size: 26px; font-weight: bold;")
        tp.v.addWidget(self.trend)
        self.strength = QProgressBar()
        self.strength.setRange(0, 100)
        self.strength.setFormat("Fuerza %p/100")
        tp.v.addWidget(self.strength)
        self.structure = QLabel("—")
        self.change = QLabel("")
        self.change.setStyleSheet(f"color:{T.AMBER}; font-weight:bold;")
        self.change.setWordWrap(True)
        tp.v.addWidget(self.structure)
        tp.v.addWidget(self.change)
        self.mtf = make_table(["Temporalidad", "Tendencia"])
        self.mtf.setMaximumHeight(170)
        tp.v.addWidget(QLabel("Multi-temporalidad:"))
        tp.v.addWidget(self.mtf)
        root.addWidget(tp, 0, 0)

        # Técnico
        tech = Panel("Análisis técnico")
        g = QGridLayout()
        self.lbl = {}
        for i, key in enumerate(["EMA 9", "EMA 21", "EMA 200", "MACD", "Señal MACD", "Histograma MACD", "ATR", "Volumen"]):
            g.addWidget(QLabel(key + ":"), i, 0)
            self.lbl[key] = QLabel("—")
            self.lbl[key].setStyleSheet(f"color:{T.CYAN};")
            g.addWidget(self.lbl[key], i, 1)
        tech.v.addLayout(g)
        tech.v.addWidget(QLabel("RSI (zonas 30 / 70):"))
        self.rsi = GaugeBar(0, 100, [(0, 30, T.GREEN), (70, 100, T.RED)])
        tech.v.addWidget(self.rsi)
        self.rsi_lbl = QLabel("—")
        tech.v.addWidget(self.rsi_lbl)
        self.levels = make_table(["Nivel", "Tipo", "Toques"])
        self.levels.setMaximumHeight(150)
        tech.v.addWidget(QLabel("Soportes y resistencias:"))
        tech.v.addWidget(self.levels)
        root.addWidget(tech, 0, 1)

        # Volatilidad + probabilidad
        vp = Panel("Volatilidad y probabilidad histórica")
        self.vol = QLabel("—")
        self.vol.setStyleSheet("font-size: 18px; font-weight: bold;")
        vp.v.addWidget(self.vol)
        vp.v.addWidget(QLabel("ATR actual / mediana (zona extrema > umbral):"))
        self.vol_gauge = GaugeBar(0, 4, [(0, 0.7, T.CYAN_DIM), (1.4, 2.5, T.AMBER), (2.5, 4, T.RED)])
        vp.v.addWidget(self.vol_gauge)
        self.prob = QLabel("—")
        self.prob.setWordWrap(True)
        vp.v.addWidget(QLabel("Probabilidad histórica de éxito de la estrategia:"))
        vp.v.addWidget(self.prob)
        disclaimer = QLabel("La puntuación de confluencia NO es una probabilidad. La probabilidad histórica proviene "
                            "solo de operaciones simuladas/backtest reales del sistema, con su intervalo de confianza.")
        disclaimer.setWordWrap(True)
        disclaimer.setObjectName("subtitle")
        vp.v.addWidget(disclaimer)
        self.btn_refresh = QPushButton("Recalcular análisis ahora")
        self.btn_refresh.clicked.connect(self._force)
        vp.v.addWidget(self.btn_refresh)
        vp.v.addStretch(1)
        root.addWidget(vp, 0, 2)

        # Confluencia
        fp = Panel("Factores de confluencia (COMPRA vs VENTA)")
        h = QHBoxLayout()
        self.long_tbl = make_table(["Factor COMPRA", "✓", "Peso", "Detalle"])
        self.short_tbl = make_table(["Factor VENTA", "✓", "Peso", "Detalle"])
        h.addWidget(self.long_tbl)
        h.addWidget(self.short_tbl)
        fp.v.addLayout(h, 1)
        self.scores = QLabel("—")
        self.scores.setStyleSheet("font-weight:bold;")
        fp.v.addWidget(self.scores)
        root.addWidget(fp, 1, 0, 1, 2)

        ep = Panel("Explicación de la IA")
        self.explain = QLabel("—")
        self.explain.setWordWrap(True)
        ep.v.addWidget(self.explain)
        ep.v.addStretch(1)
        root.addWidget(ep, 1, 2)
        root.setRowStretch(1, 1)
        for col in range(3):
            root.setColumnStretch(col, 1)
        self._mtf_counter = 0

    def _force(self) -> None:
        self.ctrl._last_bar_time = None
        try:
            self.ctrl._analyze_if_new_bar(force=True)
        except Exception as exc:  # noqa: BLE001
            self.explain.setText(f"Error: {exc}")
        self._mtf_counter = 0
        self.refresh()

    def refresh(self) -> None:
        a = self.ctrl.analysis
        if a is None:
            return
        col = T.GREEN if a.trend == "alcista" else T.RED if a.trend == "bajista" else T.AMBER
        self.trend.setText(f"{a.trend.upper()}  ·  {a.price:.2f}")
        self.trend.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {col};")
        self.strength.setValue(int(a.trend_strength))
        self.structure.setText(f"Estructura: {a.structure} · {a.timeframe} · vela {a.time:%Y-%m-%d %H:%M}")
        self.change.setText(f"⚠ Cambio de tendencia detectado: {a.trend_change}" if a.trend_change else "")
        if self._mtf_counter % 10 == 0:
            trends = self.ctrl.multi_timeframe_trends()
            fill_table(self.mtf, [[k, v] for k, v in trends.items()],
                       [{1: T.GREEN if v == "alcista" else T.RED if v == "bajista" else T.AMBER} for v in trends.values()])
        self._mtf_counter += 1
        vals = {"EMA 9": f"{a.ema_fast:.2f}", "EMA 21": f"{a.ema_mid:.2f}", "EMA 200": f"{a.ema_slow:.2f}",
                "MACD": f"{a.macd:+.3f}", "Señal MACD": f"{a.macd_signal:+.3f}", "Histograma MACD": f"{a.macd_hist:+.3f}",
                "ATR": f"{a.atr:.2f} USD", "Volumen": a.volume_state}
        for k, v in vals.items():
            self.lbl[k].setText(v)
        self.rsi.set_value(a.rsi)
        zone = "sobrecompra" if a.rsi > 70 else "sobreventa" if a.rsi < 30 else "neutral"
        self.rsi_lbl.setText(f"RSI {a.rsi:.1f} ({zone})")
        fill_table(self.levels, [[f"{lv.price:.2f}", lv.kind, lv.touches] for lv in a.levels],
                   [{1: T.GREEN if lv.kind == "soporte" else T.RED} for lv in a.levels])
        vcol = {"extrema": T.RED, "alta": T.AMBER, "baja": T.CYAN_DIM}.get(a.volatility_state, T.GREEN)
        self.vol.setText(f"Volatilidad {a.volatility_state.upper()} (x{a.atr_ratio:.2f})")
        self.vol.setStyleSheet(f"font-size: 18px; font-weight: bold; color:{vcol};")
        self.vol_gauge.set_value(a.atr_ratio)
        best = max(a.long_eval, a.short_eval, key=lambda e: e.score)
        est = self.ctrl.calibrator.estimate(best.score)
        self.prob.setText(est["text"])
        self.prob.setStyleSheet(f"color:{T.TEXT if est['sufficient'] else T.AMBER};")
        for tbl, ev in ((self.long_tbl, a.long_eval), (self.short_tbl, a.short_eval)):
            fill_table(tbl, [[f.label, "✔" if f.passed else "✖", f.weight, f.detail] for f in ev.factors],
                       [{1: T.GREEN if f.passed else T.RED} for f in ev.factors])
        self.scores.setText(
            f"COMPRA {a.long_eval.score:.0f}/100 ({a.long_eval.confluence} factores) · filtros: "
            f"{', '.join(a.long_eval.filters) or 'ninguno'}   |   VENTA {a.short_eval.score:.0f}/100 "
            f"({a.short_eval.confluence} factores) · filtros: {', '.join(a.short_eval.filters) or 'ninguno'}   |   "
            f"Mínimo: {self.ctrl.cfg.strategy.min_confluence} factores y {self.ctrl.cfg.strategy.min_score:.0f} puntos")
        text = "\n".join(a.summary_lines())
        if a.signal:
            text += f"\n\nSEÑAL ACTIVA: {a.signal.explanation}"
        last = next(iter(self.ctrl.signals), None)
        if last:
            text += (f"\n\nÚltima señal ({last.signal.time:%H:%M}): {last.signal.side} "
                     f"{'ACEPTADA' if last.accepted else 'RECHAZADA'} — {last.reason}")
        self.explain.setText(text)
