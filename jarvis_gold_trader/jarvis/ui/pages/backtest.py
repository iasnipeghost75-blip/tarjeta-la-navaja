"""BACKTESTING & VALIDACIÓN — entrenamiento/validación, fuera de muestra y referencias."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from ...backtest import format_metrics, run_validation
from ...backtest.report import comparison_rows, equity_figure, write_html_report
from ...config import PROJECT_ROOT, VALID_TIMEFRAMES
from ...core import TradingController
from .. import theme as T
from ..widgets import Panel, PlotlyView
from .common import fill_table, make_table


class _Worker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, cfg, candles, folds: int) -> None:
        super().__init__()
        self.cfg, self.candles, self.folds = cfg, candles, folds

    def run(self) -> None:
        try:
            rep = run_validation(self.cfg, self.candles, progress=self.progress.emit, walk_forward_folds=self.folds)
            self.finished.emit(rep)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class BacktestPage(QWidget):
    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        self.report = None
        self.report_path = None
        self._thread: QThread | None = None
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Velas:"))
        self.bars = QSpinBox()
        self.bars.setRange(1000, 200000)
        self.bars.setSingleStep(1000)
        self.bars.setValue(ctrl.cfg.backtest.bars)
        bar.addWidget(self.bars)
        bar.addWidget(QLabel("Temporalidad:"))
        self.tf = QComboBox()
        self.tf.addItems(list(VALID_TIMEFRAMES))
        self.tf.setCurrentText(ctrl.tf)
        bar.addWidget(self.tf)
        bar.addWidget(QLabel("Semilla (sintético):"))
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(ctrl.cfg.backtest.seed)
        bar.addWidget(self.seed)
        bar.addWidget(QLabel("Walk-forward (bloques):"))
        self.folds = QSpinBox()
        self.folds.setRange(0, 10)
        self.folds.setValue(0)
        bar.addWidget(self.folds)
        self.b_run = QPushButton("▶ EJECUTAR BACKTEST Y VALIDACIÓN")
        self.b_run.clicked.connect(self.start)
        self.b_open = QPushButton("Abrir informe HTML")
        self.b_open.setEnabled(False)
        self.b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.report_path))))
        bar.addStretch(1)
        bar.addWidget(self.b_run)
        bar.addWidget(self.b_open)
        root.addLayout(bar)

        note = QLabel("Se elige la configuración SOLO con el tramo de entrenamiento y se evalúa una vez fuera de muestra. "
                      "Incluye spread, comisión y deslizamiento; ejecución en la apertura de la vela siguiente. "
                      "Con la fuente sintética los resultados no representan el mercado real.")
        note.setWordWrap(True)
        note.setObjectName("subtitle")
        root.addWidget(note)

        split = QSplitter(Qt.Vertical)
        top = QSplitter(Qt.Horizontal)
        cp = Panel("Comparativa con estrategias de referencia")
        self.comp = make_table(["Estrategia", "Ops", "Acierto", "PF", "Expectativa", "Neto", "DD máx %"])
        cp.v.addWidget(self.comp)
        self.verdict = QLabel("Ejecute un backtest para obtener un veredicto.")
        self.verdict.setWordWrap(True)
        cp.v.addWidget(self.verdict)
        top.addWidget(cp)
        mp = Panel("Métricas fuera de muestra")
        self.metrics = make_table(["Métrica", "Valor"])
        mp.v.addWidget(self.metrics)
        top.addWidget(mp)
        top.setSizes([700, 420])
        split.addWidget(top)
        bottom = QSplitter(Qt.Horizontal)
        gp = Panel("Curvas de equity")
        self.plot = PlotlyView(min_height=260)
        gp.v.addWidget(self.plot)
        bottom.addWidget(gp)
        lp = Panel("Progreso")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lp.v.addWidget(self.log)
        bottom.addWidget(lp)
        bottom.setSizes([760, 360])
        split.addWidget(bottom)
        root.addWidget(split, 1)

    @property
    def running(self) -> bool:
        return self._thread is not None

    def start(self) -> None:
        if self.running:
            return
        self.log.clear()
        try:
            candles, self.source_label = self.ctrl.historical_candles(self.tf.currentText(), self.bars.value(),
                                                                      seed=self.seed.value())
        except Exception as exc:  # noqa: BLE001
            self.log.appendPlainText(f"✖ No se pudieron obtener datos históricos: {exc}")
            return
        self.log.appendPlainText(f"Datos: {self.source_label} · {len(candles)} velas {self.tf.currentText()}")
        self.b_run.setEnabled(False)
        self._thread = QThread(self)
        self._worker = _Worker(self.ctrl.cfg, candles, self.folds.value())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.log.appendPlainText)
        self._worker.finished.connect(self._done)
        self._worker.failed.connect(self._fail)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._candles_len = len(candles)
        self._thread.start()

    def _cleanup(self) -> None:
        self._thread = None
        self.b_run.setEnabled(True)

    def _fail(self, msg: str) -> None:
        self.log.appendPlainText(f"✖ Error: {msg}")

    def _done(self, rep) -> None:
        self.report = rep
        rows = comparison_rows(rep)
        fill_table(self.comp, [list(r.values()) for r in rows])
        fill_table(self.metrics, format_metrics(rep.test.metrics))
        ok = "✓ Expectativa positiva" in rep.verdict
        self.verdict.setText(rep.verdict)
        self.verdict.setStyleSheet(f"color:{T.GREEN if ok else T.AMBER};")
        self.plot.show_figure(equity_figure(rep))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_path = write_html_report(rep, PROJECT_ROOT / "reports" / f"backtest_{stamp}.html", self.source_label)
        self.b_open.setEnabled(True)
        self.ctrl.set_calibrator(rep.calibrator)
        self.ctrl.db.save_backtest(self.source_label, self.tf.currentText(), self._candles_len, rep.best_params,
                                   rep.train.metrics, rep.test.metrics,
                                   {k: (v.metrics if hasattr(v, "metrics") else {kk: vv for kk, vv in v.items() if kk != "equity"})
                                    for k, v in rep.benchmarks.items()}, rep.verdict, str(self.report_path))
        self.log.appendPlainText(f"✔ Informe guardado: {self.report_path}")
        self.log.appendPlainText("✔ Calibración de confianza actualizada con resultados fuera de muestra.")
