"""Confianza estadística de las señales basada en resultados históricos REALES del sistema.

La tasa de acierto se calcula a partir de operaciones de backtesting o de la
simulación, agrupadas por tramo de puntuación de confluencia, y se acompaña de
un intervalo de Wilson al 95 %. Si no hay suficientes operaciones, se informa
explícitamente "datos insuficientes" en lugar de inventar un porcentaje.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

BUCKETS = [(0, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bucket_of(score: float) -> str:
    for lo, hi in BUCKETS:
        if lo <= score < hi:
            return f"{lo}-{min(hi, 100)}"
    return "90-100"


@dataclass
class BucketStats:
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0

    @property
    def n(self) -> int:
        return self.wins + self.losses


@dataclass
class ConfidenceCalibrator:
    min_trades: int = 20
    source: str = "sin datos"
    buckets: dict[str, BucketStats] = field(default_factory=dict)

    def add(self, score: float, pnl: float) -> None:
        b = self.buckets.setdefault(bucket_of(score), BucketStats())
        if pnl > 0:
            b.wins += 1
        else:
            b.losses += 1
        b.pnl += pnl

    def fit(self, trades: list[tuple[float, float]], source: str) -> "ConfidenceCalibrator":
        self.buckets = {}
        for score, pnl in trades:
            self.add(score, pnl)
        self.source = source
        return self

    @property
    def total(self) -> BucketStats:
        t = BucketStats()
        for b in self.buckets.values():
            t.wins += b.wins
            t.losses += b.losses
            t.pnl += b.pnl
        return t

    def estimate(self, score: float) -> dict:
        b = self.buckets.get(bucket_of(score))
        scope = f"tramo {bucket_of(score)}"
        if b is None or b.n < self.min_trades:
            b = self.total
            scope = "todas las señales"
        if b.n < self.min_trades:
            return {"sufficient": False, "n": b.n, "scope": scope, "source": self.source,
                    "text": f"Datos insuficientes ({b.n} operaciones < {self.min_trades}). Ejecute un backtest."}
        lo, hi = wilson_interval(b.wins, b.n)
        rate = b.wins / b.n
        return {"sufficient": True, "n": b.n, "win_rate": rate, "ci_low": lo, "ci_high": hi,
                "avg_pnl": b.pnl / b.n, "scope": scope, "source": self.source,
                "text": (f"Acierto histórico {rate:.1%} (IC95 {lo:.1%}–{hi:.1%}, n={b.n}, {scope}, fuente: "
                         f"{self.source}). Rendimiento pasado no garantiza resultados futuros.")}

    def to_dict(self) -> dict:
        return {"min_trades": self.min_trades, "source": self.source,
                "buckets": {k: [v.wins, v.losses, v.pnl] for k, v in self.buckets.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceCalibrator":
        c = cls(min_trades=int(d.get("min_trades", 20)), source=d.get("source", "sin datos"))
        for k, (w, lo, p) in d.get("buckets", {}).items():
            c.buckets[k] = BucketStats(int(w), int(lo), float(p))
        return c
