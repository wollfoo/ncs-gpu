#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

python3 -m venv "$ROOT_DIR/.venv"
source "$ROOT_DIR/.venv/bin/activate"
pip install -U pip
pip install -r "$ROOT_DIR/requirements.txt"

uvicorn appgpu.infrastructure.api.main:app --host 0.0.0.0 --port 9000

