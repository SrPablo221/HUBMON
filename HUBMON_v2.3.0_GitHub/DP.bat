@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Execute INSTALAR.bat antes de usar este atalho.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "%~dp0trocar.py" dp
if errorlevel 1 pause
