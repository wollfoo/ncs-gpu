#!/usr/bin/env bash
set -euo pipefail

# Wrapper: compile rules -> validate -> assemble developer instructions -> (optionally) run your runner
# Usage examples:
#   bash .codex/scripts/run_codex.sh --core-only --runner-cmd 'node path/to/runner.js'
#   bash .codex/scripts/run_codex.sh --dry-run

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
OUT_DIR="$ROOT_DIR/out"
DEV_FILE="$OUT_DIR/dev_instructions_active.md"
RULES_INDEX="$OUT_DIR/rules.index.json"

CORE_ONLY=0
NO_VALIDATE=0
DRY_RUN=0
RUNNER_CMD=""
OUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-only) CORE_ONLY=1; shift;;
    --no-validate) NO_VALIDATE=1; shift;;
    --runner-cmd) RUNNER_CMD="$2"; shift 2;;
    --out|-o) OUT_FILE="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help)
      cat <<EOF
Usage: bash .codex/scripts/run_codex.sh [options]
  --core-only        Load only core rules (activation=always_on OR tag=codex_cli_core)
  --no-validate      Skip validator (faster, less safe)
  --runner-cmd CMD   Run your runner with env vars set (e.g., 'node app.js')
  --out FILE         Write developer instructions to FILE as well
  --dry-run          Build and print locations, but do not run runner
  -h, --help         Show this help
EOF
      exit 0
      ;;
    *) echo "[run_codex] Unknown option: $1" >&2; exit 2;;
  esac
done

echo "[run_codex] Compiling rules..." >&2
bash "$SCRIPTS_DIR/compile_rules.sh"

if [[ "$NO_VALIDATE" -ne 1 ]]; then
  echo "[run_codex] Validating rules..." >&2
  python3 "$SCRIPTS_DIR/validate_rules.py"
fi

echo "[run_codex] Assembling developer instructions..." >&2
mkdir -p "$OUT_DIR"
if [[ "$CORE_ONLY" -eq 1 ]]; then
  python3 "$SCRIPTS_DIR/load_rules.py" --core-only > "$DEV_FILE"
else
  python3 "$SCRIPTS_DIR/load_rules.py" > "$DEV_FILE"
fi

[[ -n "$OUT_FILE" ]] && cp "$DEV_FILE" "$OUT_FILE"

echo "[run_codex] Developer instructions: $DEV_FILE" >&2
echo "[run_codex] Rules index:           $RULES_INDEX" >&2

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[run_codex] Dry run complete. Skipping runner." >&2
  exit 0
fi

if [[ -n "$RUNNER_CMD" ]]; then
  echo "[run_codex] Running: $RUNNER_CMD" >&2
  CODEX_DEV_INSTRUCTIONS_FILE="$DEV_FILE" \
  CODEX_RULES_INDEX="$RULES_INDEX" \
  bash -lc "$RUNNER_CMD"
else
  cat <<EOF >&2
[run_codex] No --runner-cmd provided. Export the following env vars in your runner:
  CODEX_DEV_INSTRUCTIONS_FILE=$DEV_FILE
  CODEX_RULES_INDEX=$RULES_INDEX
Then inject the content of \$CODEX_DEV_INSTRUCTIONS_FILE as the developer instructions
before creating the session (Responses API: instructions=..., or chat: role=developer message).
EOF
fi
