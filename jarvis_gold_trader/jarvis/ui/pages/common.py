"""Utilidades compartidas por las páginas."""

from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from .. import theme as T


def make_table(headers: Sequence[str], stretch_last: bool = True) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(list(headers))
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_last:
        t.horizontalHeader().setStretchLastSection(True)
    return t


def fill_table(t: QTableWidget, rows: Iterable[Sequence], colors: Iterable[dict | None] | None = None) -> None:
    rows = list(rows)
    colors = list(colors) if colors is not None else [None] * len(rows)
    t.setUpdatesEnabled(False)
    t.setRowCount(len(rows))
    for i, row in enumerate(rows):
        cmap = colors[i] or {}
        for j, val in enumerate(row):
            item = t.item(i, j)
            text = "" if val is None else str(val)
            if item is None:
                item = QTableWidgetItem(text)
                t.setItem(i, j, item)
            elif item.text() != text:
                item.setText(text)
            item.setForeground(QColor(cmap.get(j, T.TEXT)))
            item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignRight if isinstance(val, (int, float)) else Qt.AlignLeft))
    t.setUpdatesEnabled(True)


def money(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v:+,.2f}" if sign else f"{v:,.2f}"
