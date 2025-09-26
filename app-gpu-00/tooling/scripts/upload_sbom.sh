#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SBOM_REGISTRY_URL:-}" ]]; then
  echo "SBOM_REGISTRY_URL is not set; skipping upload" >&2
  exit 0
fi

if [[ -z "${SBOM_REGISTRY_TOKEN:-}" ]]; then
  echo "SBOM_REGISTRY_TOKEN is not set; aborting" >&2
  exit 1
fi

ARTIFACT_PATH=${1:-}
if [[ -z "$ARTIFACT_PATH" ]]; then
  echo "Usage: $0 <sbom-file>" >&2
  exit 1
fi

if [[ ! -f "$ARTIFACT_PATH" ]]; then
  echo "SBOM file $ARTIFACT_PATH not found" >&2
  exit 1
fi

artifact_name=${SBOM_ARTIFACT_NAME:-$(basename "$ARTIFACT_PATH")}

curl -sSf -X PUT \
  -H "Authorization: Bearer ${SBOM_REGISTRY_TOKEN}" \
  -H "Content-Type: application/json" \
  --data-binary "@${ARTIFACT_PATH}" \
  "${SBOM_REGISTRY_URL%/}/${artifact_name}"

echo "SBOM uploaded to ${SBOM_REGISTRY_URL}/${artifact_name}"
