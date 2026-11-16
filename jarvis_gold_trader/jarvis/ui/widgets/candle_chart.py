"""Gráfico de velas holográfico en tiempo real (QPainter, sin parpadeo).

Muestra velas XAUUSD, EMA 9/21/200, soportes/resistencias, señales detectadas,
posiciones simuladas (entrada, SL, TP) y la cotización Bid/Ask actual.
Incluye retícula con lectura OHLC al pasar el ratón y zoom con la rueda.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .. import theme as T


@dataclass
class ChartMarker:
    time: pd.Timestamp
    price: float
    side: str  # BUY / SELL
    accepted: bool


@dataclass
class ChartPosition:
    id: int
    side: str
    entry: float
    sl: float
    tp: float
    pnl: float


class CandleChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 320)
        self.setMouseTracking(True)
        self.df: pd.DataFrame = pd.DataFrame()
        self.overlays: dict[str, pd.Series] = {}
        self.levels: list[tuple[float, str]] = []
        self.markers: list[ChartMarker] = []
        self.positions: list[ChartPosition] = []
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None
        self.visible_bars = 90
        self.title = "XAUUSD"
        self.show_emas = True
        self.show_levels = True
        self._mouse: Optional[QPointF] = None
        self._scan = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._anim)
        self._timer.start(50)

    # ------------------------------------------------------------------- datos
    def set_data(self, df: pd.DataFrame, overlays: dict[str, pd.Series] | None = None,
                 levels: list[tuple[float, str]] | None = None, markers: list[ChartMarker] | None = None,
                 positions: list[ChartPosition] | None = None, bid: float | None = None, ask: float | None = None,
                 title: str | None = None) -> None:
        self.df = df.reset_index(drop=True)
        self.overlays = overlays or {}
        self.levels = levels or []
        self.markers = markers or []
        self.positions = positions or []
        self.bid, self.ask = bid, ask
        if title:
            self.title = title
        self.update()

    def _anim(self) -> None:
        if self.isVisible():
            self._scan = (self._scan + 0.006) % 1.0
            self.update()

    def wheelEvent(self, e) -> None:
        delta = e.angleDelta().y()
        self.visible_bars = int(max(30, min(300, self.visible_bars * (0.85 if delta > 0 else 1.15))))
        self.update()

    def mouseMoveEvent(self, e) -> None:
        self._mouse = e.position()

    def leaveEvent(self, _e) -> None:
        self._mouse = None

    # ----------------------------------------------------------------- dibujo
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, QColor("#030d1b"))
        bg.setColorAt(1, QColor("#01060d"))
        p.fillRect(self.rect(), bg)
        plot = QRectF(10, 28, W - 86, H - 52)
        # retícula holográfica
        p.setPen(QPen(T.qc(T.CYAN, 18), 1))
        step = 28
        x = plot.left()
        while x < plot.right():
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            x += step
        y = plot.top()
        while y < plot.bottom():
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            y += step
        p.setPen(QPen(T.qc(T.CYAN, 90), 1))
        p.drawRect(plot)
        # esquinas HUD
        p.setPen(QPen(T.qc(T.CYAN), 2))
        c = 14
        for (cx, cy, dx, dy) in [(plot.left(), plot.top(), 1, 1), (plot.right(), plot.top(), -1, 1),
                                 (plot.left(), plot.bottom(), 1, -1), (plot.right(), plot.bottom(), -1, -1)]:
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx * c, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * c))
        f = QFont("Consolas", 9)
        p.setFont(f)
        p.setPen(T.qc(T.CYAN))
        p.drawText(QPointF(14, 18), f"{self.title} · SIMULACIÓN")
        if self.df.empty:
            p.setPen(T.qc(T.MUTED))
            p.drawText(plot, Qt.AlignCenter, "ESPERANDO DATOS DE MERCADO…")
            p.end()
            return
        d = self.df.tail(self.visible_bars).reset_index()
        offset = int(d["index"].iloc[0])
        n = len(d)
        prices = [d["low"].min(), d["high"].max()]
        for key, s in self.overlays.items():
            seg = s.iloc[offset:offset + n].dropna()
            if len(seg) and key != "ema_slow":
                prices += [seg.min(), seg.max()]
        if self.bid:
            prices += [self.bid, self.ask or self.bid]
        for pos in self.positions:
            prices += [pos.entry]
        lo, hi = min(prices), max(prices)
        pad = (hi - lo) * 0.08 or 1
        lo, hi = lo - pad, hi + pad

        def yp(v: float) -> float:
            return plot.bottom() - (v - lo) / (hi - lo) * plot.height()

        bw = plot.width() / max(n, 1)

        def xp(i: int) -> float:
            return plot.left() + bw * (i + 0.5)

        # eje de precios
        p.setPen(T.qc(T.MUTED))
        for k in range(6):
            v = lo + (hi - lo) * k / 5
            p.drawText(QPointF(plot.right() + 6, yp(v) + 4), f"{v:,.2f}")
        # eje de tiempo
        times = pd.to_datetime(d["time"])
        for i in range(0, n, max(1, n // 6)):
            p.drawText(QPointF(xp(i) - 18, plot.bottom() + 15), times.iloc[i].strftime("%H:%M"))
        p.save()
        p.setClipRect(plot)
        # soportes/resistencias
        if self.show_levels:
            for price, kind in self.levels:
                col = T.GREEN if kind == "soporte" else T.RED
                p.setPen(QPen(T.qc(col, 110), 1, Qt.DashLine))
                p.drawLine(QPointF(plot.left(), yp(price)), QPointF(plot.right(), yp(price)))
                p.drawText(QPointF(plot.left() + 4, yp(price) - 3), f"{kind.upper()} {price:.2f}")
        # velas
        for i, r in enumerate(d.itertuples()):
            up = r.close >= r.open
            col = T.GREEN if up else T.RED
            x = xp(i)
            p.setPen(QPen(T.qc(col, 200), 1))
            p.drawLine(QPointF(x, yp(r.high)), QPointF(x, yp(r.low)))
            top, bot = yp(max(r.open, r.close)), yp(min(r.open, r.close))
            body = QRectF(x - bw * 0.35, top, bw * 0.7, max(1.0, bot - top))
            p.setBrush(T.qc(col, 150 if up else 170))
            p.drawRect(body)
        # medias móviles
        if self.show_emas:
            colors = {"ema_fast": T.CYAN, "ema_mid": T.GOLD, "ema_slow": T.MAGENTA}
            for key, s in self.overlays.items():
                seg = s.iloc[offset:offset + n].reset_index(drop=True)
                path = QPainterPath()
                started = False
                for i, v in enumerate(seg):
                    if v is None or (isinstance(v, float) and math.isnan(v)):
                        continue
                    pt = QPointF(xp(i), yp(float(v)))
                    if not started:
                        path.moveTo(pt)
                        started = True
                    else:
                        path.lineTo(pt)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(T.qc(colors.get(key, T.TEXT), 220), 1.6))
                p.drawPath(path)
        # EMA lenta fuera del rango visible: indicador en el borde
        slow = self.overlays.get("ema_slow")
        if self.show_emas and slow is not None and len(slow) and pd.notna(slow.iloc[-1]):
            v = float(slow.iloc[-1])
            if v > hi or v < lo:
                p.setPen(T.qc(T.MAGENTA))
                yy = plot.top() + 14 if v > hi else plot.bottom() - 6
                p.drawText(QPointF(plot.right() - 150, yy), f"EMA200 {v:.2f} {'▲' if v > hi else '▼'}")
        # señales
        tindex = {pd.Timestamp(t): i for i, t in enumerate(times)}
        for m in self.markers:
            i = tindex.get(pd.Timestamp(m.time))
            if i is None:
                continue
            x = xp(i)
            col = T.GREEN if m.side == "BUY" else T.RED
            alpha = 255 if m.accepted else 110
            if m.side == "BUY":
                yb = yp(d["low"].iloc[i]) + 8
                tri = QPolygonF([QPointF(x, yb), QPointF(x - 6, yb + 10), QPointF(x + 6, yb + 10)])
            else:
                yb = yp(d["high"].iloc[i]) - 8
                tri = QPolygonF([QPointF(x, yb), QPointF(x - 6, yb - 10), QPointF(x + 6, yb - 10)])
            p.setPen(QPen(T.qc(col, alpha), 1))
            p.setBrush(T.qc(col, alpha if m.accepted else 40))
            p.drawPolygon(tri)
        # posiciones simuladas
        for pos in self.positions:
            col = T.GREEN if pos.side == "BUY" else T.RED
            p.setPen(QPen(T.qc(col, 200), 1.2))
            p.drawLine(QPointF(plot.left(), yp(pos.entry)), QPointF(plot.right(), yp(pos.entry)))
            p.drawText(QPointF(plot.right() - 170, yp(pos.entry) - 3),
                       f"#{pos.id} {pos.side} {pos.entry:.2f}  {pos.pnl:+.2f}$")
            p.setPen(QPen(T.qc(T.RED, 120), 1, Qt.DotLine))
            p.drawLine(QPointF(plot.right() - 120, yp(pos.sl)), QPointF(plot.right(), yp(pos.sl)))
            p.setPen(QPen(T.qc(T.GREEN, 120), 1, Qt.DotLine))
            if pos.tp > 0:
                p.drawLine(QPointF(plot.right() - 120, yp(pos.tp)), QPointF(plot.right(), yp(pos.tp)))
        # línea de escaneo animada
        sy = plot.top() + plot.height() * self._scan
        grad = QLinearGradient(0, sy - 30, 0, sy)
        grad.setColorAt(0, T.qc(T.CYAN, 0))
        grad.setColorAt(1, T.qc(T.CYAN, 35))
        p.fillRect(QRectF(plot.left(), sy - 30, plot.width(), 30), grad)
        p.restore()
        # bid/ask
        if self.bid:
            for val, col, lbl in ((self.bid, T.CYAN, "BID"), (self.ask, T.GOLD, "ASK")):
                if not val:
                    continue
                p.setPen(QPen(T.qc(col, 160), 1, Qt.DashLine))
                p.drawLine(QPointF(plot.left(), yp(val)), QPointF(plot.right(), yp(val)))
                box = QRectF(plot.right() + 2, yp(val) - 8, 74, 16)
                p.fillRect(box, T.qc(col, 200))
                p.setPen(QColor("#00121d"))
                p.drawText(box, Qt.AlignCenter, f"{lbl} {val:.2f}")
        # retícula del ratón
        if self._mouse is not None and plot.contains(self._mouse):
            mx, my = self._mouse.x(), self._mouse.y()
            p.setPen(QPen(T.qc(T.CYAN, 120), 1, Qt.DashLine))
            p.drawLine(QPointF(plot.left(), my), QPointF(plot.right(), my))
            p.drawLine(QPointF(mx, plot.top()), QPointF(mx, plot.bottom()))
            i = int((mx - plot.left()) / bw)
            if 0 <= i < n:
                r = d.iloc[i]
                price = lo + (plot.bottom() - my) / plot.height() * (hi - lo)
                txt = (f"{pd.Timestamp(r.time):%Y-%m-%d %H:%M}  O {r.open:.2f}  H {r.high:.2f}  "
                       f"L {r.low:.2f}  C {r.close:.2f}  V {r.volume:,.0f}  ·  cursor {price:.2f}")
                p.setPen(T.qc(T.TEXT))
                p.drawText(QPointF(plot.left() + 4, H - 4), txt)
        # leyenda
        p.setPen(T.qc(T.CYAN))
        lx = W - 330
        for key, col, lbl in (("ema_fast", T.CYAN, "EMA9"), ("ema_mid", T.GOLD, "EMA21"), ("ema_slow", T.MAGENTA, "EMA200")):
            p.setPen(QPen(T.qc(col), 3))
            p.drawLine(QPointF(lx, 14), QPointF(lx + 16, 14))
            p.setPen(T.qc(col))
            p.drawText(QPointF(lx + 20, 18), lbl)
            lx += 75
        p.end()
