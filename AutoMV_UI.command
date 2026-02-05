#!/bin/bash
# AutoMV UI — Double-click to launch
# Creates a virtual environment if needed, installs dependencies, and starts the Gradio UI.

cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo "==============================="
echo "  AutoMV — Music Video Generator"
echo "==============================="
echo ""

# ── Check Python 3 ────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: Python 3 is required but not found."
    echo "Install it from https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

echo "Using Python: $($PYTHON --version)"
echo ""

# ── Clone AutoMV repo if missing ──────────────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/AutoMV_repo" ]; then
    echo "Cloning AutoMV repository..."
    git clone https://github.com/multimodal-art-projection/AutoMV.git "$SCRIPT_DIR/AutoMV_repo"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to clone AutoMV repository."
        echo "Check your internet connection and try again."
        read -p "Press Enter to close..."
        exit 1
    fi
    echo ""
fi

# ── Create virtual environment if missing ─────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv "$SCRIPT_DIR/venv"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment."
        read -p "Press Enter to close..."
        exit 1
    fi
    echo ""
fi

# ── Activate venv ─────────────────────────────────────────────────────────────
source "$SCRIPT_DIR/venv/bin/activate"

# ── Install / update dependencies ─────────────────────────────────────────────
echo "Checking dependencies..."
pip install --quiet --upgrade gradio python-dotenv
echo ""

# ── Launch the UI ─────────────────────────────────────────────────────────────
echo "Starting AutoMV UI..."
echo "Open http://localhost:7860 in your browser"
echo "Press Ctrl+C to stop"
echo ""

python "$SCRIPT_DIR/app.py"

echo ""
read -p "Press Enter to close..."
