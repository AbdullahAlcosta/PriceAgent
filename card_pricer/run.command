#!/bin/bash
# Card Pricing Agent — double-click launcher for Mac/Linux.
# First run: sets everything up (takes a few minutes).
# Every run after: starts instantly.

cd "$(dirname "$0")"

VENV_DIR="venv"
SETUP_MARKER="$VENV_DIR/.setup_complete"

if [ ! -f "$SETUP_MARKER" ]; then
    echo "=========================================="
    echo "  First-time setup — this only happens once"
    echo "=========================================="
    echo ""

    if ! command -v python3 &> /dev/null; then
        echo "Python 3 isn't installed on this computer."
        echo "Please install it from https://www.python.org/downloads/ and then run this again."
        read -p "Press Enter to close..."
        exit 1
    fi

    echo "Setting up (this can take a few minutes)..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    playwright install chromium

    touch "$SETUP_MARKER"
    echo ""
    echo "Setup complete!"
    echo ""
else
    source "$VENV_DIR/bin/activate"
fi

python launcher.py
