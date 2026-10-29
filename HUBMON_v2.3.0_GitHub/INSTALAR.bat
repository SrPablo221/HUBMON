@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================
echo  HUBMON 2.3.0 - instalacao para Windows
echo ==============================================
echo.
echo O instalador cria um ambiente Python isolado nesta pasta.
echo E necessaria conexao com a internet durante a instalacao
echo para baixar a dependencia monitorcontrol do PyPI.
echo.

set "PY_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    where python >nul 2>&1
    if %errorlevel%==0 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo ERRO: Python 3.10 ou superior nao foi encontrado.
    echo Instale Python 3.10+ em https://www.python.org/downloads/windows/
    echo Durante a instalacao, marque a opcao para adicionar Python ao PATH.
    pause
    exit /b 1
)

echo Criando ambiente virtual...
%PY_CMD% -m venv ".venv"
if errorlevel 1 goto erro_venv

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro_pip

echo.
echo Instalacao concluida. Agora abra HUBMON.bat.
pause
exit /b 0

:erro_venv
echo.
echo ERRO: nao foi possivel criar o ambiente virtual.
echo Verifique sua instalacao do Python e tente novamente.
pause
exit /b 1

:erro_pip
echo.
echo ERRO: nao foi possivel instalar as dependencias.
echo Confira sua conexao com a internet e tente executar INSTALAR.bat novamente.
echo Se o erro continuar, copie a mensagem exibida e abra uma issue no GitHub.
pause
exit /b 1
