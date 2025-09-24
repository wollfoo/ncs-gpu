#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

function usage() {
  echo "Usage: $0 [up|down|logs]" >&2
  exit 1
}

case "${1:-}" in
  up)
    (cd "$ROOT_DIR" && docker compose up -d --build)
    ;;
  down)
    (cd "$ROOT_DIR" && docker compose down -v)
    ;;
  logs)
    (cd "$ROOT_DIR" && docker compose logs -f)
    ;;
  *)
    usage
    ;;
esac
