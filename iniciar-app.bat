@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 goto :error

    echo Instalando dependencias do projeto...
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m app.main
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Falha ao preparar ou iniciar o app.
pause
exit /b 1
