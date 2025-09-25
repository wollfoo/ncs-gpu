#!/usr/bin/env bash
set -euo pipefail

COUNT=${1:-100}
CONCURRENCY=${CONCURRENCY:-4}
URL=${SCHEDULER_URL:-http://127.0.0.1:8080/jobs}
TOKEN=${SCHEDULER_BENCH_TOKEN:-}

payload_template='{"payload":{"kind":"bench","seq":SEQ}}'

echo "Running scheduler benchmark: count=${COUNT}, concurrency=${CONCURRENCY}, url=${URL}" >&2

run_call() {
  local seq_id="$1"
  local payload=${payload_template//SEQ/${seq_id}}
  if [[ -n "$TOKEN" ]]; then
    curl -sS -X POST "$URL" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "$payload" >/dev/null
  else
    curl -sS -X POST "$URL" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null
  fi
}

export -f run_call
export URL TOKEN payload_template

seq 1 "$COUNT" | xargs -n1 -P "$CONCURRENCY" bash -c 'run_call "$0"'

echo "Completed benchmark run" >&2
