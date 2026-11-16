"""Generador de mercado sintético de XAUUSD (modo SIMULATION).

Produce precios con cambios de régimen (tendencia alcista, bajista, rango),
volatilidad estocástica, spread variable y volumen correlacionado con el
movimiento. Es reproducible mediante semilla. Los datos son FICTICIOS y solo
sirven para probar el sistema sin conexión a MetaTrader 5.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .base import CANDLE_COLUMNS, TIMEFRAME_MINUTES, DataError, MarketDataProvider, Tick, resample_candles

# drift por minuto (log-retorno) de cada régimen
_REGIME_DRIFT = {0: 0.0, 1: 0.000045, 2: -0.000045}
_REGIME_NAMES = {0: "rango", 1: "tendencia alcista", 2: "tendencia bajista"}


class SyntheticGoldProvider(MarketDataProvider):
    name = "synthetic"
    is_synthetic = True

    def __init__(self, seed: int = 7, start_price: float = 2350.0, history_minutes: int = 20000,
                 seconds_per_tick: int = 15, base_spread: float = 0.25,
                 start_time: datetime | None = None, symbol: str = "XAUUSD") -> None:
        super().__init__()
        self.symbol = symbol
        self.rng = np.random.default_rng(seed)
        self.seconds_per_tick = max(1, int(seconds_per_tick))
        self.base_spread = base_spread
        self.history_minutes = int(history_minutes)
        self._price = float(start_price)
        self._anchor = float(start_price)
        self._regime = 0
        self._vol = 1.0  # multiplicador de volatilidad estocástica
        self._sigma_min = 0.00032  # volatilidad base por minuto (~0.75 USD a 2350)
        start = start_time or datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
        self._start_time = start
        self._m1_rows: list[tuple] = []
        self._forming: list | None = None  # [time, o, h, l, c, v]
        self._now = start
        self._cache: dict[str, tuple[int, pd.DataFrame]] = {}
        self._last_tick: Tick | None = None
        self._pending_spike: float = 0.0
        self._pending_error: bool = False
        self._generate_history()

    # ------------------------------------------------------------------ régimen
    def _update_state(self, dt_min: float) -> None:
        p_switch = 0.0025 * dt_min
        if self.rng.random() < p_switch:
            self._regime = int(self.rng.choice([0, 1, 2], p=[0.4, 0.3, 0.3]))
            self._anchor = self._price
        # volatilidad estocástica con reversión a 1
        self._vol += 0.02 * (1.0 - self._vol) * dt_min + 0.04 * math.sqrt(dt_min) * self.rng.standard_normal()
        if self.rng.random() < 0.0008 * dt_min:  # ráfagas ocasionales (noticias)
            self._vol += self.rng.uniform(0.8, 1.6)
        self._vol = float(np.clip(self._vol, 0.4, 4.0))

    def _next_return(self, dt_min: float) -> float:
        drift = _REGIME_DRIFT[self._regime] * dt_min
        if self._regime == 0:  # reversión a la media en rango
            drift += -0.02 * math.log(self._price / self._anchor) * dt_min
        shock = self._sigma_min * self._vol * math.sqrt(dt_min) * self.rng.standard_t(5) / math.sqrt(5 / 3)
        return drift + shock

    @property
    def regime_name(self) -> str:
        return _REGIME_NAMES[self._regime]

    # ---------------------------------------------------------------- historial
    def _generate_history(self) -> None:
        t = self._start_time
        for _ in range(self.history_minutes):
            self._update_state(1.0)
            o = self._price
            # 4 sub-pasos para un rango intrabar realista
            hi = lo = o
            p = o
            for _k in range(4):
                p *= math.exp(self._next_return(0.25))
                hi, lo = max(hi, p), min(lo, p)
            self._price = p
            vol = float(self.rng.lognormal(4.0, 0.35) * (1 + 40 * abs(math.log(p / o)) / self._sigma_min * 0.01))
            self._m1_rows.append((t, o, hi, lo, p, round(vol)))
            t += timedelta(minutes=1)
        self._now = t
        self._forming = [t, self._price, self._price, self._price, self._price, 0.0]

    # ------------------------------------------------------------------ eventos
    def inject_volatility_spike(self, usd: float = 25.0) -> None:
        """Provoca un salto brusco de precio en el próximo tick (prueba de protecciones)."""
        self._pending_spike = float(usd)

    def inject_data_error(self) -> None:
        """Provoca un tick corrupto en el próximo paso (prueba de pausa automática)."""
        self._pending_error = True

    # -------------------------------------------------------------------- API
    def connect(self) -> None:
        self.connected = True

    def current_spread(self) -> float:
        return round(self.base_spread * (0.8 + 0.25 * self._vol) + abs(self.rng.normal(0, 0.03)), 2)

    def step(self) -> Tick:
        if not self.connected:
            raise DataError("Proveedor sintético no conectado")
        dt_sec = self.seconds_per_tick
        dt_min = dt_sec / 60.0
        self._update_state(dt_min)
        prev_price = self._price
        self._price *= math.exp(self._next_return(dt_min))
        if self._pending_spike:
            self._price += self._pending_spike
            self._anchor = self._price
            self._pending_spike = 0.0
        new_now = self._now + timedelta(seconds=dt_sec)
        # cierre de velas M1 cuando cambia el minuto
        f = self._forming
        assert f is not None
        while new_now >= f[0] + timedelta(minutes=1):
            self._m1_rows.append(tuple(f))
            nt = f[0] + timedelta(minutes=1)
            self._forming = f = [nt, prev_price, prev_price, prev_price, prev_price, 0.0]
        f[2] = max(f[2], self._price)
        f[3] = min(f[3], self._price)
        f[4] = self._price
        tick_vol = float(round(self.rng.lognormal(2.6, 0.4) * (1 + abs(self._price - prev_price))))
        f[5] += tick_vol
        self._now = new_now
        spread = self.current_spread()
        bid = round(self._price - spread / 2, 2)
        ask = round(bid + spread, 2)
        if self._pending_error:
            self._pending_error = False
            tick = Tick(time=new_now, bid=float("nan"), ask=float("nan"), volume=tick_vol)
        else:
            tick = Tick(time=new_now, bid=bid, ask=ask, volume=tick_vol)
        self._last_tick = tick
        return tick

    @property
    def now(self) -> datetime:
        return self._now

    def _m1_frame(self) -> pd.DataFrame:
        n = len(self._m1_rows)
        cached = self._cache.get("_m1")
        if cached and cached[0] == n:
            return cached[1]
        if cached and cached[0] < n:  # añadir solo las velas nuevas
            new = pd.DataFrame(self._m1_rows[cached[0]:], columns=CANDLE_COLUMNS)
            new["time"] = pd.to_datetime(new["time"], utc=True)
            df = pd.concat([cached[1], new], ignore_index=True)
        else:
            df = pd.DataFrame(self._m1_rows, columns=CANDLE_COLUMNS)
            df["time"] = pd.to_datetime(df["time"], utc=True)
        self._cache["_m1"] = (n, df)
        return df

    def get_candles(self, timeframe: str, count: int, include_forming: bool = False) -> pd.DataFrame:
        if timeframe not in TIMEFRAME_MINUTES:
            raise DataError(f"Temporalidad no soportada: {timeframe}")
        n = len(self._m1_rows)
        key = f"{timeframe}:{count}"
        cached = self._cache.get(key)
        minutes = TIMEFRAME_MINUTES[timeframe]
        if cached and cached[0] == n:
            full = cached[1]
        else:
            m1_all = self._m1_frame()
            # solo se remuestrea la cola necesaria; la primera vela puede quedar incompleta y se descarta
            m1 = m1_all.tail((count + 2) * minutes) if minutes > 1 else m1_all.tail(count)
            full = resample_candles(m1, timeframe)
            if minutes > 1 and len(m1) < len(m1_all) and len(full):
                full = full.iloc[1:]
            # la última vela agregada puede estar incompleta: solo es "cerrada" si su fin <= reloj de la última M1 cerrada
            if minutes > 1 and len(full):
                last_closed_end = m1["time"].iloc[-1] + pd.Timedelta(minutes=1)
                if full["time"].iloc[-1] + pd.Timedelta(minutes=minutes) > last_closed_end:
                    full = full.iloc[:-1]
            full = full.reset_index(drop=True)
            self._cache[key] = (n, full)
        out = full
        if include_forming:
            out = pd.concat([full, self._forming_bar(timeframe)], ignore_index=True)
        return out.tail(count).reset_index(drop=True)

    def _forming_bar(self, timeframe: str) -> pd.DataFrame:
        minutes = TIMEFRAME_MINUTES[timeframe]
        f = self._forming
        assert f is not None
        start = pd.Timestamp(f[0]).floor(f"{minutes}min")
        m1 = self._m1_frame()
        part = m1[m1["time"] >= start]
        rows = [tuple(r) for r in part.itertuples(index=False)] + [tuple(f)]
        o = rows[0][1]
        h = max(r[2] for r in rows)
        lo = min(r[3] for r in rows)
        c = rows[-1][4]
        v = sum(r[5] for r in rows)
        df = pd.DataFrame([(start, o, h, lo, c, v)], columns=CANDLE_COLUMNS)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        return df

    def has_real_volume(self) -> bool:
        return True  # volumen sintético coherente con el movimiento


def generate_synthetic_candles(bars: int, timeframe: str = "M5", seed: int = 11,
                               start_price: float = 2350.0) -> pd.DataFrame:
    """Serie histórica sintética para backtesting (sin bucle de ticks)."""
    minutes = TIMEFRAME_MINUTES[timeframe]
    prov = SyntheticGoldProvider(seed=seed, start_price=start_price, history_minutes=bars * minutes + minutes)
    prov.connect()
    m1 = prov._m1_frame()
    df = resample_candles(m1, timeframe)
    return df.tail(bars).reset_index(drop=True)
