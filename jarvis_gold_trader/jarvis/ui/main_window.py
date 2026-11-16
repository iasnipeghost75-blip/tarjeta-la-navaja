"""Ventana principal de JARVIS AI GOLD TRADER."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, SIMULATION_BANNER, __version__
from ..core import TradingController
from . import theme as T
from .pages import AnalysisPage, BacktestPage, DashboardPage, HistoryPage, LivePage, SettingsPage
from .widgets import StatusLed, glow

NAV = [("dashboard", "◉  DASHBOARD"), ("live", "▤  LIVE TRADING SIMULATOR"), ("analysis", "◈  AI MARKET ANALYSIS"),
       ("history", "≡  TRADE HISTORY"), ("backtest", "⟲  BACKTESTING"), ("settings", "⚙  SETTINGS")]


class MainWindow(QMainWindow):
    def __init__(self, ctrl: TradingController, confirm_dialogs: bool = True) -> None:
        super().__init__()
        self.ctrl = ctrl
        self.confirm_dialogs = confirm_dialogs
        self.steps_per_tick = 1
        self.setWindowTitle(f"{APP_NAME} v{__version__} — SIMULACIÓN")
        self.resize(1500, 920)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---------------------------------------------------------- cabecera
        header = QWidget()
        header.setStyleSheet(f"background: rgba(4,16,31,0.95); border-bottom: 1px solid {T.BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 10, 18, 10)
        title_box = QVBoxLayout()
        title = QLabel("J.A.R.V.I.S  ·  AI GOLD TRADER")
        title.setObjectName("title")
        glow(title, T.CYAN, 22)
        sub = QLabel("XAUUSD · ANÁLISIS CUANTITATIVO · SIMULADOR MULTIOPERACIÓN")
        sub.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        hl.addLayout(title_box)
        hl.addStretch(1)
        self.banner = QLabel("⚠ " + SIMULATION_BANNER)
        self.banner.setObjectName("banner")
        hl.addWidget(self.banner)
        hl.addStretch(1)
        self.mode_chip = QLabel(f"MODO {ctrl.mode.value}")
        self.mode_chip.setObjectName("chip")
        self.src_chip = QLabel("")
        self.src_chip.setObjectName("chip")
        self.clock = QLabel("")
        self.clock.setObjectName("chip")
        self.led = StatusLed(T.GREEN)
        for w in (self.mode_chip, self.src_chip, self.clock, self.led):
            hl.addWidget(w)
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        nav = QWidget()
        nav.setFixedWidth(250)
        nav.setStyleSheet(f"background: rgba(3,12,24,0.95); border-right: 1px solid {T.BORDER};")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(0, 16, 0, 16)
        nl.setSpacing(2)
        self.stack = QStackedWidget()
        self.pages = {
            "dashboard": DashboardPage(ctrl), "live": LivePage(ctrl), "analysis": AnalysisPage(ctrl),
            "history": HistoryPage(ctrl), "backtest": BacktestPage(ctrl), "settings": SettingsPage(ctrl),
        }
        self.nav_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in NAV:
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, k=key: self.show_page(k))
            group.addButton(b)
            nl.addWidget(b)
            self.nav_buttons[key] = b
            self.stack.addWidget(self.pages[key])
        nl.addStretch(1)
        self.quick = QLabel("")
        self.quick.setWordWrap(True)
        self.quick.setStyleSheet(f"color:{T.MUTED}; padding: 10px; font-size: 11px;")
        nl.addWidget(self.quick)
        self.emerg = QPushButton("⛔ EMERGENCIA")
        self.emerg.setObjectName("danger")
        self.emerg.clicked.connect(self.emergency)
        nl.addWidget(self.emerg)
        foot = QLabel("Sin dinero real · Sin órdenes reales\nSin credenciales almacenadas")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet(f"color:{T.MUTED}; font-size: 10px; padding: 8px;")
        nl.addWidget(foot)
        body.addWidget(nav)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.addWidget(self.stack)
        body.addWidget(content, 1)
        outer.addLayout(body, 1)

        self.pages["dashboard"].emergency_requested.connect(self.emergency)
        self.pages["live"].speed_changed.connect(self.set_speed)
        self.show_page("dashboard")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(max(50, ctrl.cfg.market.tick_interval_ms))

    # ---------------------------------------------------------------- acciones
    def show_page(self, key: str) -> None:
        self.nav_buttons[key].setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        page = self.pages[key]
        if key == "history":
            page.refresh(force=True)
        elif hasattr(page, "refresh") and key not in ("settings", "backtest"):
            page.refresh()

    def set_speed(self, steps: int) -> None:
        self.steps_per_tick = max(1, int(steps))

    def emergency(self) -> None:
        if self.confirm_dialogs:
            r = QMessageBox.warning(self, "PARADA DE EMERGENCIA",
                                    "Se cerrarán TODAS las posiciones simuladas, se desactivará el auto-trading y se "
                                    "bloquearán nuevas entradas. ¿Confirmar?", QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self.ctrl.emergency_stop()
        self.refresh_visible()

    # ----------------------------------------------------------------- bucle
    def on_timer(self) -> None:
        try:
            for _ in range(self.steps_per_tick):
                self.ctrl.step()
                if not self.ctrl.running:
                    break
        except Exception as exc:  # noqa: BLE001 - nunca romper el bucle de la UI
            self.ctrl._data_pause(f"Excepción en el ciclo: {exc}")
        self.pages["dashboard"].record_equity()
        self.refresh_visible()

    def refresh_visible(self) -> None:
        s = self.ctrl.snapshot()
        t = s["time"]
        self.clock.setText(f"{t:%Y-%m-%d %H:%M:%S} UTC" if hasattr(t, "strftime") else str(t))
        self.src_chip.setText(("DATOS SINTÉTICOS" if s["synthetic"] else s["source"])[:40])
        color = T.RED if s["blocked"] else T.AMBER if (s["volatility_block"] or not s["running"]) else T.GREEN
        self.led.set_color(color, blink=color != T.GREEN)
        self.quick.setText(f"EQUITY {s['equity']:,.2f} $\nFLOTANTE {s['floating']:+,.2f} $\n"
                           f"POSICIONES {s['open_positions']} · {s['total_lots']:.2f} lotes\n{s['status']}")
        current = self.stack.currentWidget()
        if current is self.pages["history"]:
            current.refresh(force=False)
        elif current not in (self.pages["settings"], self.pages["backtest"]):
            current.refresh()

    def closeEvent(self, e) -> None:
        self.timer.stop()
        self.ctrl.stop()
        super().closeEvent(e)
