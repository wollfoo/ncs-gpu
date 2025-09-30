#!/usr/bin/env bash
set -euo pipefail

# **[Run Docker]** (chạy bằng Docker – bật GPU, seccomp, non-root)
IMAGE=${IMAGE:-api-models:latest}
PORT=${PORT:-8080}

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image $IMAGE not found. Build with: make docker-build" >&2
  exit 1
fi

docker run --rm -it \
  --gpus all \
  --user 1000:1000 \
  --security-opt seccomp=$(pwd)/scripts/seccomp-profile.json \
  -p ${PORT}:8080 \
  "$IMAGE"
