"""Visor de figuras Plotly dentro de PySide6.

Usa QWebEngineView cuando está disponible. Si no lo está (o se define la
variable ``JARVIS_NO_WEBENGINE=1``), muestra un gráfico nativo equivalente con
las mismas series, de modo que la interfaz nunca queda vacía.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import plotly.graph_objects as go
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QStackedLayout, QWidget

from .hud import LineChart


def webengine_available() -> bool:
    if os.environ.get("JARVIS_NO_WEBENGINE") == "1":
        return False
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        return True
    except Exception:
        return False


class PlotlyView(QWidget):
    def __init__(self, parent: QWidget | None = None, min_height: int = 260) -> None:
        super().__init__(parent)
        self.setMinimumHeight(min_height)
        self._stack = QStackedLayout(self)
        self.fallback = LineChart(self)
        self.web = None
        if webengine_available():
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.web = QWebEngineView(self)
            self.web.page().setBackgroundColor("#020812")
            self._stack.addWidget(self.web)
        self._stack.addWidget(self.fallback)
        self._tmp = Path(tempfile.gettempdir()) / f"jarvis_plot_{id(self)}.html"
        self.last_figure: go.Figure | None = None

    @property
    def uses_webengine(self) -> bool:
        return self.web is not None

    def show_figure(self, fig: go.Figure) -> None:
        self.last_figure = fig
        if self.web is not None:
            # plotly.js embebido: funciona sin conexión a Internet
            html = fig.to_html(include_plotlyjs=True, full_html=True, config={"displaylogo": False})
            html = html.replace("<head>", "<head><style>body{margin:0;background:#020812}</style>", 1)
            self._tmp.write_text(html, encoding="utf-8")
            self.web.load(QUrl.fromLocalFile(str(self._tmp)))
            self._stack.setCurrentWidget(self.web)
        else:
            series = []
            for tr in fig.data:
                if isinstance(tr, go.Scatter) and tr.y is not None and len(tr.y) > 1:
                    color = (tr.line.color if tr.line and tr.line.color else "#00e5ff")
                    series.append((list(tr.y), color, tr.name or ""))
            if not series:
                for tr in fig.data:
                    if tr.y is not None and len(tr.y) > 1:
                        cum, acc = [], 0.0
                        for v in tr.y:
                            acc += float(v)
                            cum.append(acc)
                        series.append((cum, "#00e5ff", (tr.name or "") + " (acumulado)"))
            self.fallback.set_multi(series[:5])
            self._stack.setCurrentWidget(self.fallback)
