# JARVIS AI GOLD TRADER

Sistema modular en Python para **analizar XAUUSD, detectar oportunidades y simular la gestión de múltiples posiciones**, con una interfaz holográfica estilo JARVIS (PySide6), backtesting con validación fuera de muestra y base de datos SQLite.

> ⚠️ **SOLO SIMULACIÓN / DEMO.** JARVIS no envía órdenes a ningún bróker, no usa dinero real, no pide ni guarda contraseñas y el modo LIVE no existe en el código. Todos los resultados son simulados. El rendimiento pasado (o simulado) no garantiza resultados futuros. Esto no es asesoramiento financiero.

---

## 1. Instalación

Requisitos: Python 3.10+.

```bash
cd jarvis_gold_trader
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

`MetaTrader5` se instala solo en Windows (marcador de plataforma en `requirements.txt`). En Linux/macOS el sistema funciona con datos sintéticos o CSV.

## 2. Uso

```bash
python main.py                         # interfaz gráfica
python run_backtest.py                 # backtest + validación por consola (datos sintéticos)
python run_backtest.py --tf M15 --bars 20000 --walk-forward 4
python run_backtest.py --csv data/xauusd_m5.csv --tf M5
python run_backtest.py --mt5 --bars 30000          # Windows + MT5 con cuenta DEMO
python -m pytest -q                    # pruebas automatizadas
```

### Fuentes de datos (`config → market.data_source`)

| Fuente | Modo | Descripción |
|---|---|---|
| `synthetic` (por defecto) | SIMULATION | Generador de XAUUSD con cambios de régimen, volatilidad estocástica, spread variable y volumen. Reproducible por semilla. **No representa el mercado real**: sirve para probar el sistema. |
| `csv` | SIMULATION | Reproduce un histórico vela a vela (formato `time,open,high,low,close[,volume]` o exportación MT5 con `<DATE> <TIME> ...`). |
| `mt5` | DEMO | Lee ticks y velas de MetaTrader 5 (XAUUSD, XAUUSDm, GOLD…). Requiere el terminal abierto con sesión iniciada en una **cuenta DEMO**. Si la cuenta es real, JARVIS se desconecta y se niega a arrancar. La ejecución sigue siendo local y simulada. |

Para usar MT5: abra el terminal, inicie sesión en su cuenta DEMO, y en *Settings* elija modo `DEMO` + fuente `mt5`, guarde y reinicie la aplicación. JARVIS usa `mt5.initialize()` sin credenciales: aprovecha la sesión del terminal.

## 3. Interfaz

| Sección | Qué hace (todo funcional) |
|---|---|
| **Dashboard** | Balance DEMO, equity, P/L neto, operaciones abiertas, tasa de acierto histórica (SQLite, todas las sesiones), estado del sistema, núcleo IA animado (color = estado, anillo = puntuación de confluencia), curva de equity, registro de decisiones en vivo. Botones: pausar/reanudar, auto-trading ON/OFF, **parada de emergencia**, rearmar, reanudar tras error de datos. |
| **Live Trading Simulator** | Gráfico de velas en tiempo real (M1–H1) con EMA 9/21/200, soportes/resistencias, señales (▲▼; atenuadas si fueron rechazadas), posiciones con entrada/SL/TP y Bid/Ask. Zoom con rueda, retícula OHLC. Tabla de posiciones con beneficio neto individual y acumulado. Compra/venta manual simulada (sujeta al gestor de riesgo), cerrar seleccionada/positivas/negativas/todas. Velocidad x1–x60. |
| **AI Market Analysis** | Tendencia y fuerza, cambio de tendencia (cruces EMA / CHoCH), tabla multi-temporalidad, EMAs, RSI, MACD, ATR, volumen, soportes/resistencias, volatilidad, tabla de factores de confluencia COMPRA vs VENTA, filtros de señal falsa activos, probabilidad histórica con IC 95 % y explicación textual. |
| **Trade History** | Operaciones (sesión o todas), resultados, duración, estadísticas (acierto con IC, PF, expectativa, drawdown, SQN…), gráficas Plotly de equity y P/L por operación, historial de decisiones filtrable, exportación CSV. |
| **Backtesting** | Ejecuta en segundo plano la validación completa, muestra la comparativa con referencias, métricas OOS, curvas de equity (Plotly) y genera un informe HTML. Actualiza la calibración de confianza. |
| **Settings** | Capital inicial, máximo de operaciones (total y por dirección), exposición, riesgo %, SL/TP (ATR o $ fijo), trailing, pérdida diaria, drawdown, volatilidad extrema, indicadores (periodos y activación), temporalidades, cierre inteligente, costes. Valida antes de guardar (`config/user_config.json`). Incluye pruebas de protección: evento de volatilidad y error de datos simulados. |

## 4. Arquitectura

```
jarvis_gold_trader/
├── main.py                 # GUI
├── run_backtest.py         # CLI de backtesting/validación
├── config/default_config.json
├── jarvis/
│   ├── safety.py           # modos permitidos (SIMULATION/DEMO), bloqueo LIVE, filtro de credenciales
│   ├── config.py           # dataclasses + validación + carga/guardado JSON
│   ├── data/               # synthetic.py · mt5_provider.py · csv_provider.py · validation.py
│   ├── analysis/           # indicators.py · structure.py · engine.py · confidence.py
│   ├── trading/            # simulator.py · risk.py · smart_close.py · costs.py · models.py
│   ├── backtest/           # engine.py · metrics.py · validation.py · report.py
│   ├── storage/database.py # SQLite
│   ├── core/controller.py  # orquestación independiente de la UI
│   └── ui/                 # PySide6: theme, widgets (HUD, velas, Plotly), pages
└── tests/                  # pytest
```

El **mismo** motor de análisis, gestor de riesgo, simulador y cierre inteligente se usan en vivo y en backtesting.

### Motor de análisis
Siete factores ponderados por dirección: alineación EMA 9/21, filtro EMA 200 (con pendiente), momento MACD, zona RSI, estructura de mercado (HH/HL, LH/LL y rupturas BOS), volumen y volatilidad operable. Una señal exige **≥ `min_confluence` factores (mínimo 2, por defecto 4)**, puntuación mínima, alineación EMA obligatoria y un disparador fresco (nueva confluencia, BOS o cruce). Filtros de señal falsa: sobre-extensión respecto a EMA21, volatilidad extrema, ruptura fallida reciente (trampa), divergencia RSI y mercado errático. Todas las series son causales (verificado por test) y se analizan solo velas cerradas.

**Confianza estadística:** la puntuación de confluencia **no** es una probabilidad. La "probabilidad histórica" proviene únicamente de operaciones del backtest fuera de muestra, por tramo de puntuación, con intervalo de Wilson al 95 %. Si hay menos de `min_trades_for_stats` operaciones se muestra "Datos insuficientes".

### Riesgo y multioperación
Tamaño = `balance × riesgo% / (distancia SL × 100 oz)`, redondeado hacia abajo; si ni el lote mínimo cabe, la operación se rechaza. Límites: posiciones totales y por dirección, lotes totales, spread, pérdida diaria (cierra todo y bloquea hasta el día siguiente), drawdown máximo, volatilidad extrema (ATR/mediana o salto de tick), pausa automática ante datos corruptos (reanudación manual), parada de emergencia. **Anti-martingala:** el tamaño nunca depende de pérdidas previas, no se añade a una dirección en pérdida y nunca se abre dos veces la misma señal (más enfriamiento y distancia mínima entre entradas).

### Cierre inteligente
Objetivo de grupo neto, stop de grupo, cierre de positivas al alcanzar una suma, objetivo individual neto, tiempo máximo y señal contraria confirmada. Todo neto de comisión y spread; cada decisión queda registrada (tabla `decisions`).

### Backtesting y validación
Señal en el cierre de la vela *i*, ejecución en la apertura de *i+1*; SL/TP intrabarra con supuesto pesimista (si se tocan ambos, SL primero), gaps al precio de apertura; spread, comisión y deslizamiento incluidos. Parámetros elegidos **solo** en el tramo de entrenamiento (rejilla pequeña, objetivo = expectativa penalizada por tamaño de muestra y drawdown), evaluación única fuera de muestra, walk-forward opcional, y comparación con: cruce EMA simple, entradas aleatorias con las mismas salidas y comprar-y-mantener. Métricas: profit factor, expectativa, drawdown máximo, acierto con IC, SQN, rachas. El veredicto indica explícitamente cuando **no** hay ventaja.

> Con datos sintéticos los resultados solo validan el funcionamiento del software. Para investigar una estrategia real use históricos de XAUUSD (CSV o MT5 DEMO) y muchas más velas.

## 5. Base de datos (SQLite, `data/jarvis.db`)
`sessions`, `trades` (con `simulated = 1`), `decisions`, `signals` (aceptadas/rechazadas con motivo), `equity`, `backtests`, `kv` (calibración de confianza).

## 6. Seguridad
- Solo modos `SIMULATION` y `DEMO`; `LIVE`/`REAL` lanza `SafetyViolation` (y no existe en la interfaz).
- Cuentas MT5 no DEMO rechazadas al conectar.
- Ninguna llamada de envío de órdenes (`order_send`, etc.) en el código: verificado por test.
- La configuración rechaza claves tipo contraseña/token/PIN.
- Banner permanente "MODO SIMULACIÓN" en la interfaz e informes.

## 7. Pruebas
`python -m pytest -q` cubre: seguridad y configuración, fuentes de datos (incluido un MT5 simulado con cuenta DEMO/real), indicadores y ausencia de look-ahead, motor de señales, simulador, riesgo, cierre inteligente, métricas, backtest (prefijo idéntico con datos futuros añadidos), validación, controlador + SQLite y la interfaz en modo offscreen pulsando cada botón.

Indicadores implementados en pandas/NumPy (fórmulas estándar de Wilder); si instala TA-Lib, un test verifica la equivalencia.

## 8. Extender
- Nuevo factor: añadirlo en `AnalysisEngine._factor_frames` y `FACTOR_WEIGHTS`.
- Nueva fuente: implementar `MarketDataProvider` (`connect`, `step`, `get_candles`).
- Nueva regla de cierre: `SmartCloseManager.evaluate`.
- Nueva rejilla de investigación: `run_validation(cfg, candles, grid={...})`.
