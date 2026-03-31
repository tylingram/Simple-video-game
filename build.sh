#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$PYTHON" -m pip install --quiet -r "$REPO_DIR/rts-game/requirements.txt"
"$PYTHON" -m pip install --quiet -r "$REPO_DIR/requirements-build.txt"

echo "Building..."
cd "$REPO_DIR"
"$VENV_DIR/bin/pyinstaller" game.spec --distpath dist --workpath build/pyinstaller --noconfirm

echo "Zipping..."
zip -9 -r "RTS_Game_Linux.zip" "dist/RTS Game"

echo ""
echo "Done: RTS_Game_Linux.zip"
echo "Share this file with your friends -- they just unzip and double-click 'RTS Game'."
