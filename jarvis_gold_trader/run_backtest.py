#!/usr/bin/env python3
"""Backtesting y validación desde línea de comandos.

Ejemplos:
    python run_backtest.py                          # datos sintéticos, temporalidad M5
    python run_backtest.py --bars 20000 --tf M15 --walk-forward 4
    python run_backtest.py --csv data/xauusd_m5.csv --tf M5
    python run_backtest.py --mt5 --bars 30000       # requiere Windows + MT5 con cuenta DEMO
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime


def main() -> int:
    from jarvis.backtest import format_metrics, run_validation
    from jarvis.backtest.report import comparison_rows, write_html_report
    from jarvis.config import PROJECT_ROOT, load_config, resolve_path
    from jarvis.data import MT5DemoProvider, generate_synthetic_candles, load_candles_csv, resample_candles
    from jarvis.storage import Database

    ap = argparse.ArgumentParser(description="Backtest y validación fuera de muestra de JARVIS")
    ap.add_argument("--config")
    ap.add_argument("--tf", default=None, help="M1, M5, M15, M30, H1")
    ap.add_argument("--bars", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--csv", help="Archivo CSV histórico (time, open, high, low, close[, volume])")
    ap.add_argument("--mt5", action="store_true", help="Descargar histórico de MetaTrader 5 (cuenta DEMO)")
    ap.add_argument("--walk-forward", type=int, default=0, help="Número de bloques walk-forward (0 = desactivado)")
    ap.add_argument("--no-save", action="store_true", help="No guardar en la base de datos")
    args = ap.parse_args()

    cfg = load_config(args.config)
    tf = args.tf or cfg.market.analysis_timeframe
    bars = args.bars or cfg.backtest.bars
    seed = cfg.backtest.seed if args.seed is None else args.seed
    if args.csv:
        candles = resample_candles(load_candles_csv(args.csv), tf).tail(bars).reset_index(drop=True)
        source = f"CSV {args.csv}"
    elif args.mt5:
        prov = MT5DemoProvider(cfg.market.symbol_variants)
        prov.connect()
        candles = prov.get_candles(tf, bars)
        source = f"MT5 DEMO {prov.describe()}"
        prov.disconnect()
    else:
        candles = generate_synthetic_candles(bars, tf, seed=seed, start_price=cfg.market.synthetic_start_price)
        source = f"SINTÉTICOS (semilla {seed}) — no representan el mercado real"

    print("=" * 78)
    print("JARVIS AI GOLD TRADER · BACKTEST Y VALIDACIÓN  (RESULTADOS SIMULADOS)")
    print("=" * 78)
    print(f"Datos: {source} · {len(candles)} velas {tf}")
    rep = run_validation(cfg, candles, progress=lambda m: print("  ·", m), walk_forward_folds=args.walk_forward)
    print("\nParámetros elegidos con el tramo de ENTRENAMIENTO:", rep.best_params)
    print("\nCOMPARATIVA (tramo de validación fuera de muestra):")
    rows = comparison_rows(rep)
    cols = list(rows[0])
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
    print("  " + " | ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + " | ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
    print("\nMÉTRICAS FUERA DE MUESTRA:")
    for k, v in format_metrics(rep.test.metrics):
        print(f"  {k:<32} {v}")
    print("\nVEREDICTO:\n  " + rep.verdict.replace("\n", "\n  "))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = write_html_report(rep, PROJECT_ROOT / "reports" / f"backtest_{stamp}.html", source)
    print(f"\nInforme HTML: {path}")
    if not args.no_save:
        db = Database(resolve_path(cfg.database_path))
        db.save_backtest(source, tf, len(candles), rep.best_params, rep.train.metrics, rep.test.metrics,
                         {k: (v.metrics if hasattr(v, "metrics") else {kk: vv for kk, vv in v.items() if kk != "equity"})
                          for k, v in rep.benchmarks.items()}, rep.verdict, str(path))
        db.set_kv("calibration", rep.calibrator.to_dict())
        print("Resultados y calibración de confianza guardados en", cfg.database_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
