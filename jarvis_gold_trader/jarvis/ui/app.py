"""Arranque de la aplicación gráfica."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .. import APP_NAME
from ..config import load_config
from ..core import TradingController
from ..safety import SafetyViolation
from .theme import STYLESHEET


def prepare_environment() -> None:
    """Chromium (QtWebEngine) no arranca como root sin --no-sandbox (p. ej. contenedores Linux)."""
    if sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0:
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if "--no-sandbox" not in flags:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --no-sandbox").strip()


def run(config_path: str | None = None) -> int:
    prepare_environment()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLESHEET)
    from .main_window import MainWindow

    try:
        cfg = load_config(config_path)
        ctrl = TradingController(cfg)
        ctrl.start()
    except SafetyViolation as exc:
        QMessageBox.critical(None, "Bloqueo de seguridad", str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "Error de inicio",
                             f"No se pudo iniciar JARVIS:\n{exc}\n\nRevise la configuración (Settings) o use "
                             "data_source='synthetic'.")
        return 1
    win = MainWindow(ctrl)
    win.show()
    return app.exec()
