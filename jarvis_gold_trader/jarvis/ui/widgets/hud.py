"""Componentes HUD holográficos: núcleo IA animado, tarjetas, LEDs y mini-gráficos."""

from __future__ import annotations

import math
from typing import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from .. import theme as T


def glow(widget: QWidget, color: str = T.CYAN, radius: int = 18) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(radius)
    eff.setOffset(0, 0)
    eff.setColor(T.qc(color, 160))
    widget.setGraphicsEffect(eff)


class Panel(QFrame):
    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(12, 10, 12, 12)
        self.v.setSpacing(8)
        if title:
            lbl = QLabel(title.upper())
            lbl.setObjectName("h2")
            self.v.addWidget(lbl)


class ArcReactor(QWidget):
    """Núcleo de IA animado. El color refleja el estado del sistema."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.angle = 0.0
        self.pulse = 0.0
        self.color = QColor(T.CYAN)
        self.title = "JARVIS"
        self.line1 = "INICIANDO"
        self.line2 = ""
        self.score = 0.0  # 0-100, anillo de confluencia
        self.active = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, color: str, line1: str, line2: str = "", score: float | None = None, active: bool = True) -> None:
        self.color = QColor(color)
        self.line1, self.line2 = line1, line2
        if score is not None:
            self.score = max(0.0, min(100.0, score))
        self.active = active
        self.update()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        speed = 1.6 if self.active else 0.3
        self.angle = (self.angle + speed) % 360
        self.pulse = (self.pulse + 0.06) % (2 * math.pi)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h) - 10
        cx, cy = w / 2, h / 2
        r = side / 2
        col = self.color
        # halo
        grad = QRadialGradient(QPointF(cx, cy), r)
        a = 70 + 40 * math.sin(self.pulse)
        grad.setColorAt(0.0, T.qc(col.name(), int(a)))
        grad.setColorAt(0.55, T.qc(col.name(), 18))
        grad.setColorAt(1.0, T.qc(col.name(), 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
        # anillos rotatorios segmentados
        for k, (rr, segs, width, direction, alpha) in enumerate(
                [(0.95, 24, 2, 1, 120), (0.82, 6, 5, -1, 200), (0.70, 36, 1, 1, 90)]):
            radius = r * rr
            rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
            pen = QPen(T.qc(col.name(), alpha), width)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            span = 360 / segs
            for s in range(segs):
                start = (s * span + direction * self.angle * (1 + k * 0.5)) % 360
                p.drawArc(rect, int(start * 16), int(span * 0.6 * 16))
        # anillo de confluencia (puntuación IA)
        radius = r * 0.58
        rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        p.setPen(QPen(T.qc(T.BORDER), 6))
        p.drawArc(rect, 90 * 16, -360 * 16)
        score_pen = QPen(T.qc(col.name(), 230), 6)
        score_pen.setCapStyle(Qt.RoundCap)
        p.setPen(score_pen)
        p.drawArc(rect, 90 * 16, int(-360 * 16 * self.score / 100))
        # núcleo
        core = QRadialGradient(QPointF(cx, cy), r * 0.45)
        core.setColorAt(0, T.qc("#ffffff", 60))
        core.setColorAt(0.4, T.qc(col.name(), 50))
        core.setColorAt(1, T.qc(T.BG, 230))
        p.setBrush(core)
        p.setPen(QPen(T.qc(col.name(), 120), 1))
        p.drawEllipse(QPointF(cx, cy), r * 0.45, r * 0.45)
        # textos
        p.setPen(T.qc(col.name()))
        f = QFont("Consolas", max(8, int(side / 18)))
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f)
        p.drawText(QRectF(cx - r, cy - r * 0.30, 2 * r, r * 0.2), Qt.AlignCenter, self.title)
        f2 = QFont("Consolas", max(7, int(side / 24)))
        p.setFont(f2)
        p.setPen(T.qc(T.TEXT))
        p.drawText(QRectF(cx - r * 0.42, cy - r * 0.08, r * 0.84, r * 0.2), Qt.AlignCenter, self.line1)
        p.setPen(T.qc(T.MUTED))
        p.drawText(QRectF(cx - r * 0.42, cy + r * 0.12, r * 0.84, r * 0.2), Qt.AlignCenter, self.line2)
        p.end()


class StatusLed(QWidget):
    def __init__(self, color: str = T.GREEN, size: int = 14, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size + 8, size + 8)
        self.color = QColor(color)
        self.blink = False
        self._on = True
        self._t = QTimer(self)
        self._t.timeout.connect(self._toggle)
        self._t.start(500)

    def set_color(self, color: str, blink: bool = False) -> None:
        self.color = QColor(color)
        self.blink = blink
        self.update()

    def _toggle(self) -> None:
        self._on = not self._on if self.blink else True
        if self.isVisible():
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        r = (min(self.width(), self.height()) - 8) / 2
        alpha = 255 if self._on else 60
        g = QRadialGradient(QPointF(c), r * 2)
        g.setColorAt(0, T.qc(self.color.name(), alpha))
        g.setColorAt(0.5, T.qc(self.color.name(), alpha // 3))
        g.setColorAt(1, T.qc(self.color.name(), 0))
        p.setBrush(g)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(c), r * 1.6, r * 1.6)
        p.setBrush(T.qc(self.color.name(), alpha))
        p.drawEllipse(QPointF(c), r * 0.8, r * 0.8)
        p.end()


class StatCard(QFrame):
    """Tarjeta de métrica con valor luminoso."""

    def __init__(self, title: str, value: str = "—", subtitle: str = "", color: str = T.CYAN,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumHeight(92)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(2)
        self.t = QLabel(title.upper())
        self.t.setObjectName("subtitle")
        self.val = QLabel(value)
        self.val.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
        self.sub = QLabel(subtitle)
        self.sub.setObjectName("subtitle")
        self.sub.setWordWrap(True)
        v.addWidget(self.t)
        v.addWidget(self.val)
        v.addWidget(self.sub)
        glow(self.val, color, 16)
        self._color = color

    def set(self, value: str, subtitle: str | None = None, color: str | None = None) -> None:
        self.val.setText(value)
        if subtitle is not None:
            self.sub.setText(subtitle)
        if color and color != self._color:
            self._color = color
            self.val.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
            glow(self.val, color, 16)


class LineChart(QWidget):
    """Mini-gráfico de líneas nativo (equity, rendimiento)."""

    def __init__(self, parent: QWidget | None = None, color: str = T.CYAN, title: str = "") -> None:
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.series: list[tuple[list[float], str, str]] = []
        self.color = color
        self.title = title
        self.baseline: float | None = None

    def set_series(self, values: Sequence[float], color: str | None = None, label: str = "") -> None:
        self.series = [(list(values), color or self.color, label)]
        self.update()

    def set_multi(self, series: list[tuple[Sequence[float], str, str]]) -> None:
        self.series = [(list(v), c, lbl) for v, c, lbl in series]
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(40, 18, -10, -16)
        p.setPen(QPen(T.qc(T.BORDER, 120), 1, Qt.DotLine))
        for i in range(5):
            y = rect.top() + rect.height() * i / 4
            p.drawLine(rect.left(), int(y), rect.right(), int(y))
        if self.title:
            p.setPen(T.qc(T.MUTED))
            p.drawText(rect.left(), 12, self.title)
        vals = [v for s, _, _ in self.series for v in s]
        if len(vals) < 2:
            p.setPen(T.qc(T.MUTED))
            p.drawText(rect, Qt.AlignCenter, "Sin datos suficientes")
            p.end()
            return
        lo, hi = min(vals), max(vals)
        if self.baseline is not None:
            lo, hi = min(lo, self.baseline), max(hi, self.baseline)
        if hi - lo < 1e-9:
            hi, lo = hi + 1, lo - 1
        p.setPen(T.qc(T.MUTED))
        f = QFont("Consolas", 8)
        p.setFont(f)
        p.drawText(2, rect.top() + 8, f"{hi:,.0f}")
        p.drawText(2, rect.bottom(), f"{lo:,.0f}")

        def ypos(v: float) -> float:
            return rect.bottom() - (v - lo) / (hi - lo) * rect.height()
        if self.baseline is not None:
            p.setPen(QPen(T.qc(T.MUTED, 150), 1, Qt.DashLine))
            p.drawLine(rect.left(), int(ypos(self.baseline)), rect.right(), int(ypos(self.baseline)))
        lx = rect.left()
        for values, color, label in self.series:
            if len(values) < 2:
                continue
            path = QPainterPath()
            n = len(values)
            for i, v in enumerate(values):
                x = rect.left() + rect.width() * i / (n - 1)
                (path.moveTo if i == 0 else path.lineTo)(x, ypos(v))
            fill = QPainterPath(path)
            fill.lineTo(rect.right(), rect.bottom())
            fill.lineTo(rect.left(), rect.bottom())
            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
            grad.setColorAt(0, T.qc(color, 70))
            grad.setColorAt(1, T.qc(color, 0))
            if len(self.series) == 1:
                p.fillPath(fill, grad)
            p.setPen(QPen(T.qc(color), 2))
            p.drawPath(path)
            if label:
                p.setPen(T.qc(color))
                p.drawText(lx, self.height() - 3, label)
                lx += 14 + p.fontMetrics().horizontalAdvance(label)
        p.end()


class GaugeBar(QWidget):
    """Barra horizontal con zonas (p.ej. RSI 0-100)."""

    def __init__(self, lo: float = 0, hi: float = 100, zones: Sequence[tuple[float, float, str]] = (),
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self.lo, self.hi = lo, hi
        self.zones = list(zones)
        self.value: float | None = None

    def set_value(self, v: float | None) -> None:
        self.value = v
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(2, 6, -2, -6)
        p.setPen(Qt.NoPen)
        p.setBrush(T.qc(T.BORDER, 140))
        p.drawRoundedRect(r, 4, 4)
        span = self.hi - self.lo
        for a, b, col in self.zones:
            x1 = r.left() + (a - self.lo) / span * r.width()
            x2 = r.left() + (b - self.lo) / span * r.width()
            p.setBrush(T.qc(col, 70))
            p.drawRect(QRectF(x1, r.top(), x2 - x1, r.height()))
        if self.value is not None and math.isfinite(self.value):
            x = r.left() + (min(max(self.value, self.lo), self.hi) - self.lo) / span * r.width()
            p.setBrush(T.qc(T.CYAN))
            p.drawEllipse(QPointF(x, r.center().y()), 7, 7)
        p.end()
