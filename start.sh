#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10 or newer is required."
    echo "On Debian: sudo apt install python3 python3-venv python3-tk python3-pip"
    exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m bmc_jconsole
