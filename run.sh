#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/venv"
PYTHON="${VENV_DIR}/bin/python"

# Create venv if it doesn't exist
if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" --upgrade-deps
fi

# Install/sync dependencies
"$PYTHON" -m pip install --quiet -r "$REPO_DIR/rts-game/requirements.txt"

# Launch game
exec "$PYTHON" "$REPO_DIR/rts-game/main.py"
