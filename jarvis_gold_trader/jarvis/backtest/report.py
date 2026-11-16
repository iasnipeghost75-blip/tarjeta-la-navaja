"""Informes Plotly (HTML autónomo) de backtesting y rendimiento."""

from __future__ import annotations

import html
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .metrics import format_metrics
from .validation import ValidationReport

THEME = dict(template="plotly_dark", paper_bgcolor="#020812", plot_bgcolor="#03101f", font=dict(color="#9fdcff", family="Consolas, monospace"))
CYAN, GOLD, RED, GREEN, GREY = "#00e5ff", "#ffc94d", "#ff4d6d", "#2dffb3", "#5f7d95"


def equity_figure(report: ValidationReport) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12, row_heights=[0.65, 0.35],
                        subplot_titles=("Equity simulada: entrenamiento vs validación y referencias",
                                        "Drawdown (validación)"))
    tr, te = report.train.equity, report.test.equity
    fig.add_trace(go.Scatter(x=tr["time"], y=tr["equity"], name="JARVIS entrenamiento", line=dict(color=GREY)), 1, 1)
    fig.add_trace(go.Scatter(x=te["time"], y=te["equity"], name="JARVIS validación", line=dict(color=CYAN, width=2)), 1, 1)
    ema = report.benchmarks["ema_cross"].equity
    rnd = report.benchmarks["random"].equity
    bh = report.benchmarks["buy_hold"]["equity"]
    fig.add_trace(go.Scatter(x=ema["time"], y=ema["equity"], name="Cruce EMA", line=dict(color=GOLD, dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=rnd["time"], y=rnd["equity"], name="Aleatoria", line=dict(color=RED, dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=bh["time"], y=bh["equity"], name="Comprar y mantener", line=dict(color=GREEN, dash="dash")), 1, 1)
    peak = te["equity"].cummax()
    fig.add_trace(go.Scatter(x=te["time"], y=te["equity"] - peak, fill="tozeroy", name="Drawdown",
                             line=dict(color=RED)), 2, 1)
    fig.update_layout(**THEME, height=640, legend=dict(orientation="h", y=-0.12))
    return fig


def trades_figure(trades: pd.DataFrame, title: str = "Distribución de resultados por operación") -> go.Figure:
    fig = go.Figure()
    if len(trades):
        colors = [GREEN if v > 0 else RED for v in trades["net_pnl"]]
        fig.add_trace(go.Bar(x=list(range(1, len(trades) + 1)), y=trades["net_pnl"], marker_color=colors, name="Neto"))
    fig.update_layout(**THEME, title=title, height=320, xaxis_title="Operación nº", yaxis_title="USD")
    return fig


def _table(rows: list[tuple[str, str]]) -> str:
    return "<table>" + "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>" for a, b in rows) + "</table>"


def comparison_rows(report: ValidationReport) -> list[dict]:
    rows = []
    for label, m in [("JARVIS entrenamiento", report.train.metrics), ("JARVIS validación (OOS)", report.test.metrics),
                     ("Cruce EMA 9/21", report.benchmarks["ema_cross"].metrics),
                     ("Aleatoria mismas salidas", report.benchmarks["random"].metrics)]:
        pf = m["profit_factor"]
        rows.append({"Estrategia": label, "Ops": m["trades"], "Acierto": f"{m['win_rate']:.1%}",
                     "PF": "∞" if pf == math.inf else f"{pf:.2f}", "Expectativa": f"{m['expectancy']:+.2f}",
                     "Neto": f"{m['net_profit']:+,.2f}", "DD máx %": f"{m['max_drawdown_pct']:.2f}"})
    bh = report.benchmarks["buy_hold"]
    rows.append({"Estrategia": "Comprar y mantener", "Ops": 1, "Acierto": "-", "PF": "-", "Expectativa": "-",
                 "Neto": f"{bh['net_profit']:+,.2f}", "DD máx %": f"{bh['max_drawdown_pct']:.2f}"})
    return rows


def write_html_report(report: ValidationReport, path: str | Path, source_label: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    comp = comparison_rows(report)
    comp_html = "<table><tr>" + "".join(f"<th>{k}</th>" for k in comp[0]) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r.values()) + "</tr>" for r in comp) + "</table>"
    wf = ""
    if report.walk_forward:
        wf = "<h2>Walk-forward</h2><table><tr><th>Bloque</th><th>Parámetros</th><th>Ops</th><th>PF</th><th>Expectativa</th></tr>" + "".join(
            f"<tr><td>{r['fold']}</td><td>{html.escape(str(r['params']))}</td><td>{r['trades']}</td>"
            f"<td>{r['profit_factor']:.2f}</td><td>{r['expectancy']:+.2f}</td></tr>" for r in report.walk_forward) + "</table>"
    body = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>JARVIS · Informe de backtest</title>
<style>body{{background:#020812;color:#9fdcff;font-family:Consolas,monospace;margin:24px}}h1,h2{{color:#00e5ff}}
table{{border-collapse:collapse;margin:8px 0 20px}}td,th{{border:1px solid #0d3550;padding:4px 10px}}
.warn{{background:#2a0a12;border:1px solid #ff4d6d;padding:10px;color:#ffb3c1}} pre{{white-space:pre-wrap}}</style></head><body>
<h1>JARVIS AI GOLD TRADER · Informe de validación</h1>
<div class="warn">RESULTADOS SIMULADOS. Datos: {html.escape(source_label)}. Incluye spread, comisión y deslizamiento.
El rendimiento pasado no garantiza resultados futuros. No constituye asesoramiento financiero.</div>
<h2>Veredicto</h2><pre>{html.escape(report.verdict)}</pre>
<h2>Parámetros elegidos SOLO con datos de entrenamiento</h2>{_table([(k, str(v)) for k, v in report.best_params.items()])}
<p>Separación entrenamiento/validación en la vela {report.split_index} ({report.split_time}).</p>
<h2>Comparativa (tramo de validación salvo indicación)</h2>{comp_html}
<h2>Métricas fuera de muestra</h2>{_table(format_metrics(report.test.metrics))}
{equity_figure(report).to_html(full_html=False, include_plotlyjs="cdn")}
{trades_figure(report.test.trades_frame()).to_html(full_html=False, include_plotlyjs=False)}
{wf}
</body></html>"""
    path.write_text(body, encoding="utf-8")
    return path
