@echo off
setlocal

set REPO_DIR=%~dp0
set VENV_DIR=%REPO_DIR%venv
set PYTHON=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

if not exist "%PYTHON%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

echo Installing dependencies...
"%PIP%" install --quiet -r "%REPO_DIR%rts-game\requirements.txt"
"%PIP%" install --quiet -r "%REPO_DIR%requirements-build.txt"

echo Building...
cd /d "%REPO_DIR%"
"%VENV_DIR%\Scripts\pyinstaller" game.spec --distpath dist --workpath build\pyinstaller --noconfirm

echo Zipping...
powershell -Command "Compress-Archive -Path 'dist\RTS Game' -DestinationPath 'RTS_Game_Windows.zip' -CompressionLevel Optimal -Force"

echo.
echo Done: RTS_Game_Windows.zip
echo Share this file with your friends -- they just unzip and double-click "RTS Game.exe".
