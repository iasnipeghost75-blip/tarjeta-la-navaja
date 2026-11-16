"""D. TRADE HISTORY — operaciones, resultados, duración, estadísticas, gráficas y decisiones."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from ...backtest.metrics import compute_metrics, format_metrics
from ...backtest.report import THEME
from ...config import PROJECT_ROOT
from ...core import TradingController
from .. import theme as T
from ..widgets import Panel, PlotlyView
from .common import fill_table, make_table

CATEGORIES = ["TODAS", "SIGNAL", "OPEN", "CLOSE", "SMART_CLOSE", "RISK", "SYSTEM"]


def _fmt_duration(sec: float) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


class HistoryPage(QWidget):
    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Ámbito:"))
        self.scope = QComboBox()
        self.scope.addItems(["Sesión actual", "Todas las sesiones"])
        self.scope.currentIndexChanged.connect(lambda _i: self.refresh(force=True))
        bar.addWidget(self.scope)
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.clicked.connect(lambda: self.export_csv(notify=True))
        bar.addWidget(self.btn_refresh)
        bar.addWidget(self.btn_export)
        bar.addStretch(1)
        self.summary = QLabel("—")
        bar.addWidget(self.summary)
        root.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        top = QSplitter(Qt.Horizontal)
        tp = Panel("Operaciones cerradas (simuladas)")
        self.trades = make_table(["#", "Tipo", "Lotes", "Entrada", "Salida", "Apertura", "Duración", "Bruto $",
                                  "Comisión $", "Neto $", "Motivo", "Punt."])
        tp.v.addWidget(self.trades)
        top.addWidget(tp)
        sp = Panel("Estadísticas")
        self.stats = make_table(["Métrica", "Valor"])
        sp.v.addWidget(self.stats)
        top.addWidget(sp)
        top.setSizes([800, 360])
        split.addWidget(top)

        bottom = QSplitter(Qt.Horizontal)
        gp = Panel("Gráficas de rendimiento")
        self.plot = PlotlyView(min_height=240)
        gp.v.addWidget(self.plot)
        bottom.addWidget(gp)
        dp = Panel("Historial de decisiones")
        h = QHBoxLayout()
        h.addWidget(QLabel("Categoría:"))
        self.cat = QComboBox()
        self.cat.addItems(CATEGORIES)
        self.cat.currentIndexChanged.connect(lambda _i: self.refresh(force=True))
        h.addWidget(self.cat)
        h.addStretch(1)
        dp.v.addLayout(h)
        self.decisions = make_table(["Hora", "Categoría", "Acción", "Detalle"])
        dp.v.addWidget(self.decisions)
        bottom.addWidget(dp)
        bottom.setSizes([560, 600])
        split.addWidget(bottom)
        root.addWidget(split, 1)
        self._sig = None

    def _trades_df(self) -> pd.DataFrame:
        sid = self.ctrl.session_id if self.scope.currentIndex() == 0 else None
        return self.ctrl.db.trades(sid)

    def refresh(self, force: bool = False) -> None:
        df = self._trades_df()
        dec_sid = self.ctrl.session_id if self.scope.currentIndex() == 0 else None
        sig = (len(df), self.scope.currentIndex(), self.cat.currentIndex(), len(self.ctrl.decisions),
               self.ctrl.session_id)
        if not force and sig == self._sig:
            return
        self._sig = sig
        rows, colors = [], []
        for r in df.iloc[::-1].head(500).itertuples():
            rows.append([r.position_id, r.side, f"{r.volume:.2f}", f"{r.entry_price:.2f}", f"{r.exit_price:.2f}",
                         str(r.open_time)[:16].replace("T", " "), _fmt_duration(r.duration_seconds),
                         f"{r.gross_pnl:+.2f}", f"{r.commission:.2f}", f"{r.net_pnl:+.2f}", r.reason, f"{r.score:.0f}"])
            colors.append({1: T.GREEN if r.side == "BUY" else T.RED, 9: T.pnl_color(r.net_pnl)})
        fill_table(self.trades, rows, colors)
        objs = [SimpleNamespace(net_pnl=r.net_pnl, commission=r.commission, duration_seconds=r.duration_seconds)
                for r in df.itertuples()]
        init = self.ctrl.sim.initial_balance
        eq = init + df["net_pnl"].cumsum() if len(df) else pd.Series(dtype=float)
        m = compute_metrics(objs, pd.DataFrame({"equity": eq}), init)
        fill_table(self.stats, format_metrics(m))
        self.summary.setText(f"{m['trades']} operaciones · neto {m['net_profit']:+,.2f} $ (SIMULADO)")
        self._plot(df, eq)
        dec = self.ctrl.db.decisions(dec_sid, limit=400)
        cat = self.cat.currentText()
        if cat != "TODAS" and len(dec):
            dec = dec[dec["category"] == cat]
        cmap = {"OPEN": T.CYAN, "CLOSE": T.GOLD, "RISK": T.AMBER, "SYSTEM": T.MAGENTA, "SMART_CLOSE": T.GREEN,
                "SIGNAL": T.TEXT}
        fill_table(self.decisions, [[str(r.time)[:19].replace("T", " "), r.category, r.action, r.detail]
                                    for r in dec.itertuples()],
                   [{1: cmap.get(r.category, T.TEXT)} for r in dec.itertuples()])

    def _plot(self, df: pd.DataFrame, eq: pd.Series) -> None:
        fig = make_subplots(rows=2, cols=1, vertical_spacing=0.14, row_heights=[0.6, 0.4],
                            subplot_titles=("Equity realizada (simulada)", "Resultado neto por operación"))
        if len(df):
            fig.add_trace(go.Scatter(y=eq.tolist(), x=list(range(1, len(df) + 1)), name="Equity",
                                     line=dict(color=T.CYAN, width=2)), 1, 1)
            fig.add_trace(go.Bar(x=list(range(1, len(df) + 1)), y=df["net_pnl"].tolist(), name="Neto",
                                 marker_color=[T.GREEN if v > 0 else T.RED for v in df["net_pnl"]]), 2, 1)
        fig.update_layout(**THEME, height=330, showlegend=False, margin=dict(l=40, r=10, t=30, b=20))
        self.plot.show_figure(fig)

    def export_csv(self, notify: bool = False) -> str:
        out = PROJECT_ROOT / "reports"
        out.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        p1 = out / f"trades_{stamp}.csv"
        p2 = out / f"decisions_{stamp}.csv"
        self._trades_df().to_csv(p1, index=False)
        sid = self.ctrl.session_id if self.scope.currentIndex() == 0 else None
        self.ctrl.db.decisions(sid, limit=100000).to_csv(p2, index=False)
        if notify:
            QMessageBox.information(self, "Exportado", f"Archivos guardados:\n{p1}\n{p2}")
        return str(p1)
