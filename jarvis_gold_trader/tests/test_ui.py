"""Pruebas de la interfaz en modo offscreen: cada botón ejecuta una acción real."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from jarvis.core import TradingController  # noqa: E402
from jarvis.data import SyntheticGoldProvider  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from jarvis.ui.theme import STYLESHEET
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    a.setStyleSheet(STYLESHEET)
    return a


@pytest.fixture
def win(app, cfg, db, tmp_path, monkeypatch):
    import jarvis.config as jc
    monkeypatch.setattr(jc, "USER_CONFIG_PATH", tmp_path / "user.json")
    from jarvis.ui import main_window as mw
    import jarvis.ui.pages.settings as st
    monkeypatch.setattr(st, "save_config", lambda c: jc.save_config(c, tmp_path / "user.json"))
    cfg.market.history_bars = 400
    ctrl = TradingController(cfg, provider=SyntheticGoldProvider(seed=7, history_minutes=6000, seconds_per_tick=60), db=db)
    ctrl.start()
    w = mw.MainWindow(ctrl, confirm_dialogs=False)
    w.timer.stop()
    w.show()
    yield w
    w.close()


def test_all_pages_render(win):
    for _ in range(30):
        win.on_timer()
    for key in win.pages:
        win.show_page(key)
        win.refresh_visible()
        assert win.stack.currentWidget() is win.pages[key]


def test_dashboard_controls(win):
    d = win.pages["dashboard"]
    d.btn_run.click()
    assert not win.ctrl.running
    d.btn_run.click()
    assert win.ctrl.running
    d.btn_auto.click()
    assert not win.ctrl.auto_trading
    d.btn_auto.click()
    assert win.ctrl.auto_trading
    win.ctrl.manual_open("BUY")
    d.btn_emerg.click()
    assert win.ctrl.risk.state.emergency_stop and not win.ctrl.sim.positions
    d.refresh()
    assert d.btn_rearm.isEnabled()
    d.btn_rearm.click()
    assert not win.ctrl.risk.state.emergency_stop
    win.ctrl.inject_data_error()
    win.on_timer()
    d.refresh()
    assert d.btn_resume.isEnabled()
    d.btn_resume.click()
    assert not win.ctrl.risk.state.data_paused


def test_live_buttons(win, monkeypatch):
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **k: None)
    live = win.pages["live"]
    win.show_page("live")
    live.b_buy.click()
    live.b_sell.click()
    assert len(win.ctrl.sim.positions) == 2
    live.refresh()
    assert live.positions.rowCount() == 2 and live.chart.positions
    live.positions.selectRow(0)
    live.b_close.click()
    assert len(win.ctrl.sim.positions) == 1
    live.b_close_all.click()
    assert not win.ctrl.sim.positions
    live.b_buy.click()
    live.b_close_pos.click(); live.b_close_neg.click()
    assert not win.ctrl.sim.positions
    for tf in ("M1", "M15", "M30", "H1"):
        live.tf.setCurrentText(tf)
        assert not live.chart.df.empty
    live.speed.setCurrentText("x20")
    assert win.steps_per_tick == 20


def test_analysis_and_history(win):
    for _ in range(20):
        win.on_timer()
    win.show_page("analysis")
    a = win.pages["analysis"]
    a.btn_refresh.click()
    assert a.long_tbl.rowCount() >= 5 and a.trend.text() != "—"
    win.ctrl.manual_open("BUY")
    win.ctrl.close_all()
    win.show_page("history")
    h = win.pages["history"]
    assert h.trades.rowCount() >= 1 and h.stats.rowCount() > 5
    h.scope.setCurrentIndex(1)
    h.cat.setCurrentText("CLOSE")
    assert all(h.decisions.item(r, 1).text() == "CLOSE" for r in range(h.decisions.rowCount()))
    path = h.export_csv()
    import os
    assert os.path.exists(path)
    os.remove(path)


def test_settings_apply_and_validation(win):
    s = win.pages["settings"]
    s.widgets[("risk", "max_positions")].setValue(3)
    assert s.apply()
    assert win.ctrl.cfg.risk.max_positions == 3 and win.ctrl.risk.cfg.max_positions == 3
    s.widgets[("strategy", "min_confluence")].setValue(2)
    s.widgets[("risk", "max_positions_per_side")].setValue(10)  # > max_positions -> inválido
    assert not s.apply()
    s.b_revert.click()
    assert s.widgets[("risk", "max_positions_per_side")].value() == win.ctrl.cfg.risk.max_positions_per_side
    s.b_spike.click()
    assert "próximo tick" in s.status.text()
    assert s.mode_combo.findText("LIVE") == -1  # LIVE no existe en la interfaz


def test_backtest_page(win, qtbot=None):
    from PySide6.QtCore import QEventLoop, QTimer
    b = win.pages["backtest"]
    b.bars.setValue(2500)
    b.start()
    loops = 0
    while b.running and loops < 600:
        loop = QEventLoop(); QTimer.singleShot(100, loop.quit); loop.exec()
        loops += 1
    assert b.report is not None, b.log.toPlainText()
    assert b.comp.rowCount() == 5 and b.b_open.isEnabled()
    assert win.ctrl.calibrator.source == "backtest fuera de muestra"
    import os
    os.remove(b.report_path)
