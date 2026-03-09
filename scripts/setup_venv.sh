#!/usr/bin/env bash
# shellcheck disable=SC1091

# Source this script:
#   source scripts/setup_venv.sh
# It will create .venv if missing, activate it, and install project deps.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Please source this script instead of executing it:"
  echo "  source scripts/setup_venv.sh"
  exit 1
fi

set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3.11+ and try again."
  return 1
fi

if [[ ! -d .venv ]]; then
  echo "[setup] Creating virtual environment at .venv"
  python3 -m venv .venv
else
  echo "[setup] Reusing existing .venv"
fi

source .venv/bin/activate

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .

echo "[setup] Environment ready. Active Python: $(which python)"
