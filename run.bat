@echo off
setlocal

set REPO_DIR=%~dp0
set VENV_DIR=%REPO_DIR%venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%" --upgrade-deps
)

"%PYTHON%" -m pip install --quiet -r "%REPO_DIR%rts-game\requirements.txt"

"%PYTHON%" "%REPO_DIR%rts-game\main.py"
