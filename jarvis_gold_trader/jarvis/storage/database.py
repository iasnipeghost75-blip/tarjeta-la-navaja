"""Persistencia SQLite: operaciones, decisiones, señales, equity, backtests y calibración."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..trading.models import ClosedTrade, Decision

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    source TEXT NOT NULL,
    initial_balance REAL NOT NULL,
    note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    position_id INTEGER,
    side TEXT, volume REAL, entry_price REAL, exit_price REAL,
    open_time TEXT, close_time TEXT, duration_seconds REAL,
    gross_pnl REAL, commission REAL, net_pnl REAL,
    reason TEXT, score REAL, signal_id TEXT, sl REAL, tp REAL, mae REAL, mfe REAL,
    simulated INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER, time TEXT, category TEXT, action TEXT, detail TEXT, position_id INTEGER, extra TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER, signal_id TEXT, time TEXT, side TEXT, price REAL, score REAL,
    confluence INTEGER, accepted INTEGER, reason TEXT, explanation TEXT
);
CREATE TABLE IF NOT EXISTS equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER, time TEXT, balance REAL, equity REAL, open_positions INTEGER
);
CREATE TABLE IF NOT EXISTS backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT, source TEXT, timeframe TEXT, bars INTEGER, params TEXT,
    train_metrics TEXT, test_metrics TEXT, benchmarks TEXT, verdict TEXT, report_path TEXT
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id);
CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);
"""


def _iso(t: Any) -> str:
    if isinstance(t, (datetime, pd.Timestamp)):
        return t.isoformat()
    return str(t)


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    # --------------------------------------------------------------- sesiones
    def start_session(self, mode: str, source: str, initial_balance: float, note: str = "") -> int:
        cur = self._exec("INSERT INTO sessions(started_at, mode, source, initial_balance, note) VALUES (?,?,?,?,?)",
                         (datetime.now().isoformat(timespec="seconds"), mode, source, initial_balance, note))
        return int(cur.lastrowid)

    # ------------------------------------------------------------- escritura
    def save_trade(self, session_id: int, t: ClosedTrade) -> None:
        self._exec(
            "INSERT INTO trades(session_id, position_id, side, volume, entry_price, exit_price, open_time, close_time,"
            " duration_seconds, gross_pnl, commission, net_pnl, reason, score, signal_id, sl, tp, mae, mfe, simulated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (session_id, t.id, t.side, t.volume, t.entry_price, t.exit_price, _iso(t.open_time), _iso(t.close_time),
             t.duration_seconds, t.gross_pnl, t.commission, t.net_pnl, t.reason, t.score, t.signal_id, t.sl, t.tp,
             t.mae, t.mfe))

    def save_decision(self, session_id: int, d: Decision) -> None:
        self._exec("INSERT INTO decisions(session_id, time, category, action, detail, position_id, extra)"
                   " VALUES (?,?,?,?,?,?,?)",
                   (session_id, _iso(d.time), d.category, d.action, d.detail, d.position_id,
                    json.dumps(d.extra, default=str)))

    def save_signal(self, session_id: int, signal, accepted: bool, reason: str) -> None:
        self._exec("INSERT INTO signals(session_id, signal_id, time, side, price, score, confluence, accepted, reason,"
                   " explanation) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (session_id, signal.id, _iso(signal.time), signal.side, signal.price, signal.score,
                    signal.confluence, int(accepted), reason, signal.explanation))

    def save_equity(self, session_id: int, time: Any, balance: float, equity: float, open_positions: int) -> None:
        self._exec("INSERT INTO equity(session_id, time, balance, equity, open_positions) VALUES (?,?,?,?,?)",
                   (session_id, _iso(time), balance, equity, open_positions))

    def save_backtest(self, source: str, timeframe: str, bars: int, params: dict, train: dict, test: dict,
                      benchmarks: dict, verdict: str, report_path: str) -> int:
        cur = self._exec("INSERT INTO backtests(created_at, source, timeframe, bars, params, train_metrics, test_metrics,"
                         " benchmarks, verdict, report_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (datetime.now().isoformat(timespec="seconds"), source, timeframe, bars, json.dumps(params),
                          json.dumps(train, default=str), json.dumps(test, default=str),
                          json.dumps(benchmarks, default=str), verdict, report_path))
        return int(cur.lastrowid)

    def set_kv(self, key: str, value: Any) -> None:
        self._exec("INSERT INTO kv(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, json.dumps(value, default=str)))

    def get_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    # --------------------------------------------------------------- lectura
    def _frame(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._lock:
            return pd.read_sql_query(sql, self.conn, params=params)

    def trades(self, session_id: Optional[int] = None) -> pd.DataFrame:
        if session_id is None:
            return self._frame("SELECT * FROM trades ORDER BY id")
        return self._frame("SELECT * FROM trades WHERE session_id=? ORDER BY id", (session_id,))

    def decisions(self, session_id: Optional[int] = None, limit: int = 500) -> pd.DataFrame:
        if session_id is None:
            return self._frame("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,))
        return self._frame("SELECT * FROM decisions WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit))

    def signals(self, session_id: Optional[int] = None, limit: int = 200) -> pd.DataFrame:
        if session_id is None:
            return self._frame("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
        return self._frame("SELECT * FROM signals WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit))

    def equity(self, session_id: int) -> pd.DataFrame:
        return self._frame("SELECT * FROM equity WHERE session_id=? ORDER BY id", (session_id,))

    def backtests(self, limit: int = 20) -> pd.DataFrame:
        return self._frame("SELECT * FROM backtests ORDER BY id DESC LIMIT ?", (limit,))

    def sessions(self) -> pd.DataFrame:
        return self._frame("SELECT * FROM sessions ORDER BY id DESC")
