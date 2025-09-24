#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

python3 -m venv "$ROOT_DIR/.venv"
source "$ROOT_DIR/.venv/bin/activate"
pip install -U pip
pip install -r "$ROOT_DIR/requirements.txt"

if command -v cargo >/dev/null 2>&1; then
  (cd "$ROOT_DIR/rust" && cargo build --release)
fi

if command -v go >/dev/null 2>&1; then
  (cd "$ROOT_DIR/go" && go build ./...)
fi

