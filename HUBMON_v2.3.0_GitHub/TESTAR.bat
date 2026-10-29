@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Execute INSTALAR.bat antes de rodar os testes.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m py_compile hub_monitor.py trocar.py
if errorlevel 1 goto falha
".venv\Scripts\python.exe" tests\test_logic.py
if errorlevel 1 goto falha
echo.
echo Testes concluidos.
pause
exit /b 0
:falha
echo.
echo Um teste falhou. Copie a mensagem acima ao relatar o problema.
pause
exit /b 1
