"""Tema holográfico JARVIS (negro / azul oscuro / cian luminoso)."""

from __future__ import annotations

from PySide6.QtGui import QColor

BG = "#020812"
BG2 = "#04101f"
PANEL = "#061629"
BORDER = "#0d3a5c"
CYAN = "#00e5ff"
CYAN_DIM = "#0a8fb0"
TEXT = "#bfe9ff"
MUTED = "#5f8aa8"
GOLD = "#ffc94d"
GREEN = "#2dffb3"
RED = "#ff4d6d"
AMBER = "#ffae3d"
MAGENTA = "#c77dff"


def qc(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def pnl_color(v: float | None) -> str:
    if v is None:
        return TEXT
    return GREEN if v > 0 else RED if v < 0 else TEXT


STYLESHEET = f"""
* {{ font-family: "Consolas", "DejaVu Sans Mono", "Menlo", monospace; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {BG}, stop:1 #030c1a); }}
QWidget {{ background: transparent; font-size: 12px; }}
QFrame#panel, QGroupBox {{
    background: rgba(6, 22, 41, 0.85); border: 1px solid {BORDER}; border-radius: 10px;
}}
QGroupBox {{ margin-top: 16px; padding: 10px 8px 8px 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {CYAN};
    font-weight: bold; letter-spacing: 2px; }}
QLabel#title {{ color: {CYAN}; font-size: 20px; font-weight: bold; letter-spacing: 4px; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 11px; letter-spacing: 2px; }}
QLabel#h2 {{ color: {CYAN}; font-size: 14px; font-weight: bold; letter-spacing: 2px; }}
QLabel#banner {{ background: rgba(255, 77, 109, 0.12); border: 1px solid {RED}; border-radius: 6px;
    color: #ffb3c1; padding: 4px 10px; font-weight: bold; letter-spacing: 1px; }}
QLabel#chip {{ background: rgba(0, 229, 255, 0.08); border: 1px solid {CYAN_DIM}; border-radius: 10px;
    padding: 3px 10px; color: {CYAN}; }}
QPushButton {{
    background: rgba(0, 229, 255, 0.06); border: 1px solid {CYAN_DIM}; border-radius: 6px;
    padding: 7px 14px; color: {CYAN}; font-weight: bold; letter-spacing: 1px;
}}
QPushButton:hover {{ background: rgba(0, 229, 255, 0.18); border-color: {CYAN}; }}
QPushButton:pressed {{ background: rgba(0, 229, 255, 0.30); }}
QPushButton:disabled {{ color: {MUTED}; border-color: #123049; background: transparent; }}
QPushButton:checked {{ background: rgba(0, 229, 255, 0.25); border-color: {CYAN}; }}
QPushButton#nav {{ text-align: left; padding: 12px 16px; border: none; border-left: 3px solid transparent;
    border-radius: 0; background: transparent; color: {MUTED}; font-size: 12px; }}
QPushButton#nav:hover {{ color: {CYAN}; background: rgba(0,229,255,0.06); }}
QPushButton#nav:checked {{ color: {CYAN}; border-left: 3px solid {CYAN}; background: rgba(0,229,255,0.10); }}
QPushButton#buy {{ border-color: {GREEN}; color: {GREEN}; background: rgba(45,255,179,0.07); }}
QPushButton#buy:hover {{ background: rgba(45,255,179,0.2); }}
QPushButton#sell {{ border-color: {RED}; color: {RED}; background: rgba(255,77,109,0.07); }}
QPushButton#sell:hover {{ background: rgba(255,77,109,0.2); }}
QPushButton#danger {{ border: 2px solid {RED}; color: #fff; background: rgba(255,77,109,0.35);
    font-size: 13px; padding: 10px 16px; }}
QPushButton#danger:hover {{ background: rgba(255,77,109,0.6); }}
QPushButton#warn {{ border-color: {AMBER}; color: {AMBER}; background: rgba(255,174,61,0.07); }}
QTableWidget, QTableView, QListWidget, QPlainTextEdit, QTextEdit {{
    background: rgba(2, 10, 20, 0.85); border: 1px solid {BORDER}; border-radius: 6px;
    gridline-color: #0b2a42; selection-background-color: rgba(0,229,255,0.25); selection-color: #fff;
}}
QHeaderView::section {{ background: #071d33; color: {CYAN}; border: none; border-bottom: 1px solid {BORDER};
    padding: 5px; font-weight: bold; }}
QTableCornerButton::section {{ background: #071d33; border: none; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: #03111f; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 6px; color: {TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {CYAN}; }}
QComboBox QAbstractItemView {{ background: #03111f; selection-background-color: rgba(0,229,255,0.25); }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {CYAN_DIM}; border-radius: 3px; background: #03111f; }}
QCheckBox::indicator:checked {{ background: {CYAN}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 20px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QProgressBar {{ background: #03111f; border: 1px solid {BORDER}; border-radius: 4px; text-align: center; height: 12px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN_DIM}, stop:1 {CYAN}); border-radius: 3px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 6px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {CYAN}; border-bottom: 2px solid {CYAN}; }}
QToolTip {{ background: #061629; color: {TEXT}; border: 1px solid {CYAN_DIM}; }}
QScrollArea {{ border: none; }}
"""
