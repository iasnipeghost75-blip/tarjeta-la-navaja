import json
import re

import pytest

from conftest import ROOT
from jarvis.config import AppConfig, config_from_dict, load_config, save_config
from jarvis.safety import SafetyViolation, TradingMode, assert_no_credentials


@pytest.mark.parametrize("mode", ["LIVE", "live", "REAL", "production"])
def test_live_mode_is_rejected(mode):
    with pytest.raises(SafetyViolation):
        TradingMode.parse(mode)
    with pytest.raises(SafetyViolation):
        config_from_dict({"mode": mode})


@pytest.mark.parametrize("key", ["password", "mt5_password", "api_token", "secret", "pin"])
def test_credentials_are_rejected(key):
    with pytest.raises(SafetyViolation):
        assert_no_credentials({"market": {key: "x"}})


def test_allowed_keys_not_flagged():
    assert_no_credentials(AppConfig().to_dict())


def test_single_indicator_strategy_is_rejected(cfg):
    cfg.strategy.min_confluence = 1
    with pytest.raises(ValueError):
        cfg.validate()


def test_stop_loss_is_mandatory(cfg):
    cfg.risk.stop_loss_atr = 0
    cfg.risk.stop_loss_usd_points = 0
    with pytest.raises(ValueError):
        cfg.validate()


def test_mt5_requires_demo_mode(cfg):
    cfg.market.data_source = "mt5"
    with pytest.raises(ValueError):
        cfg.validate()
    cfg.mode = "DEMO"
    cfg.validate()


def test_save_and_load_roundtrip(cfg, tmp_path):
    cfg.risk.max_positions = 7
    cfg.indicators.ema_fast = 8
    p = save_config(cfg, tmp_path / "c.json")
    loaded = load_config(p)
    assert loaded.risk.max_positions == 7 and loaded.indicators.ema_fast == 8


def test_default_config_file_is_valid():
    data = json.loads((ROOT / "config" / "default_config.json").read_text(encoding="utf-8"))
    config_from_dict(data)


def test_no_real_order_execution_in_codebase():
    """Ningún módulo puede enviar órdenes reales a MetaTrader 5."""
    forbidden = re.compile(r"order_send|order_check|positions_close|TRADE_ACTION_DEAL")
    for path in (ROOT / "jarvis").rglob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), f"Ejecución real encontrada en {path}"
