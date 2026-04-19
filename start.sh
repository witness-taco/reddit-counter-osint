#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

SCRIPT_NAME="V4_hardened_reddit_active_learner.py"
VENV_DIR="venv"

echo "================================================"
echo "  Reddit Comment Deleter - Launcher   "
echo "================================================"

# 1 Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: Python 3 is not installed or not in your PATH."
    exit 1
fi

# 2 Check if venv exists; if not, create
if [ ! -d "$VENV_DIR" ]; then
    echo "[+] No virtual environment found. Creating one in './$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
    echo "[+] Virtual environment created successfully."
fi

# This is required for instances like Debian/Pop!_OS
VENV_PYTHON="./$VENV_DIR/bin/python3"

# 3 Install/Upgrade dependencies using the explicit venv binary
echo "[+] Checking dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip -q
"$VENV_PYTHON" -m pip install nodriver -q
echo "[+] Dependencies are up to date."

# 4 Run
echo "================================================"
echo "[+] Launching $SCRIPT_NAME..."
echo "================================================"
"$VENV_PYTHON" "$SCRIPT_NAME"

echo "[+] Session ended."