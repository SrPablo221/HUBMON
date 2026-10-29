@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo O HUBMON ainda nao foi instalado nesta pasta.
    echo Execute INSTALAR.bat primeiro.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" hub_monitor.py
if errorlevel 1 (
    echo.
    echo O HUBMON foi encerrado com um erro. Copie a mensagem acima para relatar o problema.
    pause
)
