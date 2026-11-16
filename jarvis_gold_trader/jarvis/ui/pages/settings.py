"""E. SETTINGS — configuración editable (capital, posiciones, indicadores, temporalidades, SL/TP, riesgo)."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ...config import VALID_TIMEFRAMES, AppConfig, save_config
from ...core import TradingController
from .. import theme as T

# (sección, campo, etiqueta, tipo, mín, máx, paso)
SPEC = {
    "Capital y posiciones": [
        ("risk", "initial_balance", "Capital inicial simulado ($)", float, 100, 10_000_000, 100),
        ("risk", "max_positions", "Máximo de operaciones simultáneas", int, 1, 50, 1),
        ("risk", "max_positions_per_side", "Máximo por dirección", int, 1, 50, 1),
        ("risk", "max_total_lots", "Exposición total máxima (lotes)", float, 0.01, 50, 0.01),
        ("risk", "max_lot_per_trade", "Lote máximo por operación", float, 0.01, 10, 0.01),
        ("risk", "risk_per_trade_pct", "Riesgo por operación (%)", float, 0.05, 5, 0.05),
    ],
    "Stop Loss / Take Profit / Trailing": [
        ("risk", "stop_loss_atr", "Stop Loss (x ATR)", float, 0.1, 10, 0.1),
        ("risk", "take_profit_atr", "Take Profit (x ATR)", float, 0.1, 20, 0.1),
        ("risk", "stop_loss_usd_points", "SL fijo en $ de precio (0 = usar ATR)", float, 0, 200, 0.5),
        ("risk", "take_profit_usd_points", "TP fijo en $ de precio (0 = usar ATR)", float, 0, 400, 0.5),
        ("risk", "trailing_enabled", "Trailing Stop simulado", bool, 0, 0, 0),
        ("risk", "trailing_activation_atr", "Activación trailing (x ATR)", float, 0.1, 10, 0.1),
        ("risk", "trailing_distance_atr", "Distancia trailing (x ATR)", float, 0.1, 10, 0.1),
    ],
    "Límites de riesgo": [
        ("risk", "daily_loss_limit_pct", "Límite de pérdida diaria (%)", float, 0.1, 50, 0.1),
        ("risk", "max_drawdown_pct", "Drawdown máximo (%)", float, 0.5, 90, 0.5),
        ("risk", "extreme_volatility_ratio", "Volatilidad extrema (ATR/mediana)", float, 1.1, 10, 0.1),
        ("risk", "max_tick_jump_usd", "Salto máximo entre ticks ($)", float, 0.5, 500, 0.5),
        ("risk", "max_spread_usd", "Spread máximo para entrar ($)", float, 0.01, 20, 0.01),
        ("risk", "block_averaging_down", "Anti-martingala: no promediar pérdidas", bool, 0, 0, 0),
    ],
    "Cierre inteligente": [
        ("smart_close", "enabled", "Cierre inteligente activo", bool, 0, 0, 0),
        ("smart_close", "group_target_usd", "Objetivo de grupo neto ($, 0=off)", float, 0, 1e6, 10),
        ("smart_close", "group_stop_usd", "Stop de grupo neto ($, 0=off)", float, 0, 1e6, 10),
        ("smart_close", "close_positive_target_usd", "Cerrar positivas al sumar ($, 0=off)", float, 0, 1e6, 10),
        ("smart_close", "individual_target_usd", "Objetivo individual neto ($, 0=off)", float, 0, 1e6, 5),
        ("smart_close", "max_bars_in_trade", "Máx. velas por operación (0=off)", int, 0, 10000, 1),
        ("smart_close", "close_on_opposite_signal", "Cerrar ante señal contraria", bool, 0, 0, 0),
    ],
    "Indicadores": [
        ("indicators", "ema_fast", "EMA rápida", int, 2, 100, 1),
        ("indicators", "ema_mid", "EMA media", int, 3, 200, 1),
        ("indicators", "ema_slow", "EMA lenta", int, 20, 400, 1),
        ("indicators", "rsi_period", "Periodo RSI", int, 2, 100, 1),
        ("indicators", "rsi_overbought", "RSI sobrecompra", float, 50, 95, 1),
        ("indicators", "rsi_oversold", "RSI sobreventa", float, 5, 50, 1),
        ("indicators", "macd_fast", "MACD rápida", int, 2, 50, 1),
        ("indicators", "macd_slow", "MACD lenta", int, 5, 100, 1),
        ("indicators", "macd_signal", "MACD señal", int, 2, 50, 1),
        ("indicators", "atr_period", "Periodo ATR", int, 2, 100, 1),
        ("indicators", "use_ema200_filter", "Usar filtro EMA 200", bool, 0, 0, 0),
        ("indicators", "use_rsi", "Usar RSI", bool, 0, 0, 0),
        ("indicators", "use_macd", "Usar MACD", bool, 0, 0, 0),
        ("indicators", "use_structure", "Usar estructura de mercado", bool, 0, 0, 0),
        ("indicators", "use_volume", "Usar volumen (si hay datos)", bool, 0, 0, 0),
    ],
    "Estrategia": [
        ("strategy", "min_confluence", "Mínimo de factores coincidentes", int, 2, 7, 1),
        ("strategy", "min_score", "Puntuación mínima (0-100)", float, 10, 100, 1),
        ("strategy", "max_extension_atr", "Filtro sobre-extensión (x ATR)", float, 0.5, 10, 0.1),
        ("strategy", "cooldown_bars", "Velas de enfriamiento", int, 0, 100, 1),
        ("strategy", "min_entry_distance_atr", "Distancia mínima entre entradas (x ATR)", float, 0, 10, 0.05),
    ],
    "Costes simulados": [
        ("costs", "spread_usd", "Spread simulado ($)", float, 0, 10, 0.01),
        ("costs", "commission_per_lot", "Comisión por lote ida/vuelta ($)", float, 0, 100, 0.5),
        ("costs", "slippage_usd", "Deslizamiento por ejecución ($)", float, 0, 10, 0.01),
    ],
}


class SettingsPage(QWidget):
    def __init__(self, ctrl: TradingController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = ctrl
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(12)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        self.widgets: dict[tuple[str, str], QWidget] = {}
        # Modo y datos
        mode = QGroupBox("MODO Y DATOS")
        fl = QFormLayout(mode)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["SIMULATION", "DEMO"])
        fl.addRow("Modo:", self.mode_combo)
        live = QLabel("LIVE: DESHABILITADO PERMANENTEMENTE")
        live.setStyleSheet(f"color:{T.RED}; font-weight:bold;")
        fl.addRow("", live)
        self.source = QComboBox()
        self.source.addItems(["synthetic", "mt5", "csv"])
        fl.addRow("Fuente de datos (reinicio):", self.source)
        self.csv_path = QLineEdit()
        self.csv_path.setPlaceholderText("data/xauusd_m1.csv")
        fl.addRow("Ruta CSV:", self.csv_path)
        self.analysis_tf = QComboBox()
        self.analysis_tf.addItems(list(VALID_TIMEFRAMES))
        fl.addRow("Temporalidad de análisis:", self.analysis_tf)
        self.tf_checks: dict[str, QCheckBox] = {}
        tfrow = QHBoxLayout()
        for tf in VALID_TIMEFRAMES:
            cb = QCheckBox(tf)
            self.tf_checks[tf] = cb
            tfrow.addWidget(cb)
        tfw = QWidget()
        tfw.setLayout(tfrow)
        fl.addRow("Temporalidades monitorizadas:", tfw)
        grid.addWidget(mode, 0, 0)

        for idx, (title, items) in enumerate(SPEC.items(), start=1):
            box = QGroupBox(title.upper())
            form = QFormLayout(box)
            for section, fieldname, label, typ, lo, hi, step in items:
                if typ is bool:
                    w = QCheckBox()
                elif typ is int:
                    w = QSpinBox()
                    w.setRange(int(lo), int(hi))
                    w.setSingleStep(int(step))
                else:
                    w = QDoubleSpinBox()
                    w.setDecimals(2)
                    w.setRange(lo, hi)
                    w.setSingleStep(step)
                self.widgets[(section, fieldname)] = w
                form.addRow(label + ":", w)
            grid.addWidget(box, idx // 3, idx % 3)

        tools = QGroupBox("PRUEBAS DE PROTECCIÓN (solo datos sintéticos)")
        tl = QVBoxLayout(tools)
        self.b_spike = QPushButton("Simular evento de volatilidad extrema")
        self.b_spike.setObjectName("warn")
        self.b_error = QPushButton("Simular error de datos (pausa automática)")
        self.b_error.setObjectName("warn")
        self.b_spike.clicked.connect(lambda: self._inject("spike"))
        self.b_error.clicked.connect(lambda: self._inject("error"))
        tl.addWidget(self.b_spike)
        tl.addWidget(self.b_error)
        self.b_reset_acc = QPushButton("Reiniciar cuenta DEMO (aplica capital inicial)")
        self.b_reset_acc.clicked.connect(self._reset_account)
        tl.addWidget(self.b_reset_acc)
        n = len(SPEC) + 1
        grid.addWidget(tools, n // 3, n % 3)

        btns = QHBoxLayout()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        btns.addWidget(self.status, 1)
        self.b_defaults = QPushButton("Restaurar valores por defecto")
        self.b_defaults.clicked.connect(self._defaults)
        self.b_revert = QPushButton("Descartar cambios")
        self.b_revert.clicked.connect(lambda: self.load_from(self.ctrl.cfg))
        self.b_apply = QPushButton("GUARDAR Y APLICAR")
        self.b_apply.clicked.connect(self.apply)
        for b in (self.b_defaults, self.b_revert, self.b_apply):
            btns.addWidget(b)
        outer.addLayout(btns)
        self.load_from(ctrl.cfg)

    # ---------------------------------------------------------------- binding
    def load_from(self, cfg: AppConfig) -> None:
        self.mode_combo.setCurrentText(cfg.trading_mode.value)
        self.source.setCurrentText(cfg.market.data_source)
        self.csv_path.setText(cfg.market.csv_path)
        self.analysis_tf.setCurrentText(cfg.market.analysis_timeframe)
        for tf, cb in self.tf_checks.items():
            cb.setChecked(tf in cfg.market.timeframes)
        for (section, fieldname), w in self.widgets.items():
            val = getattr(getattr(cfg, section), fieldname)
            if isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            else:
                w.setValue(val)
        self.status.setText("")

    def read_config(self) -> AppConfig:
        cfg = copy.deepcopy(self.ctrl.cfg)
        cfg.mode = self.mode_combo.currentText()
        cfg.market.data_source = self.source.currentText()
        cfg.market.csv_path = self.csv_path.text().strip()
        cfg.market.analysis_timeframe = self.analysis_tf.currentText()
        cfg.market.timeframes = [tf for tf, cb in self.tf_checks.items() if cb.isChecked()] or [cfg.market.analysis_timeframe]
        for (section, fieldname), w in self.widgets.items():
            val = w.isChecked() if isinstance(w, QCheckBox) else w.value()
            setattr(getattr(cfg, section), fieldname, val)
        return cfg

    def apply(self) -> bool:
        try:
            cfg = self.read_config()
            cfg.validate()
            # el modo/fuente actual se mantiene hasta reiniciar; se guarda en disco
            path = save_config(cfg)
            warnings = self.ctrl.apply_config(cfg)
        except Exception as exc:  # noqa: BLE001 - errores de validación al usuario
            self.status.setText(f"✖ {exc}")
            self.status.setStyleSheet(f"color:{T.RED};")
            return False
        self.status.setText("✔ Configuración guardada en " + str(path.name) + (". " + " ".join(warnings) if warnings else ""))
        self.status.setStyleSheet(f"color:{T.GREEN};")
        return True

    def _defaults(self) -> None:
        cfg = AppConfig()
        cfg.market.data_source = self.ctrl.cfg.market.data_source
        self.load_from(cfg)
        self.status.setText("Valores por defecto cargados: pulse GUARDAR Y APLICAR para confirmarlos.")

    def _inject(self, kind: str) -> None:
        ok = self.ctrl.inject_volatility_spike(25.0) if kind == "spike" else self.ctrl.inject_data_error()
        self.status.setText("Evento programado para el próximo tick." if ok else
                            "Solo disponible con la fuente de datos sintética.")

    def _reset_account(self) -> None:
        if self.isVisible():
            r = QMessageBox.question(self, "Reiniciar cuenta DEMO",
                                     "Se cerrarán todas las posiciones simuladas y se iniciará una nueva sesión. ¿Continuar?")
            if r != QMessageBox.Yes:
                return
        self.apply()
        self.ctrl.reset_account()
        self.status.setText(f"Cuenta DEMO reiniciada: {self.ctrl.sim.balance:,.2f} $")
