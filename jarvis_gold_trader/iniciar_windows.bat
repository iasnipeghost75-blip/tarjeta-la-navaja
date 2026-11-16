@echo off
REM JARVIS AI GOLD TRADER - lanzador para Windows (solo simulacion/DEMO)
cd /d "%~dp0"
where python >nul 2>nul || (echo Instale Python 3.10+ desde https://www.python.org y marque "Add to PATH". & pause & exit /b 1)
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo Instalando dependencias...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || (pause & exit /b 1)
echo Ejecutando pruebas...
python -m pytest -q || (echo Las pruebas fallaron. Revise la salida. & pause & exit /b 1)
echo Iniciando JARVIS...
python main.py
pause
