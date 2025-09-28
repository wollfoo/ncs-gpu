#!/usr/bin/env bash
set -euo pipefail

# Script tạo CA nội bộ và chứng thư dịch vụ cho control-plane, scheduler, executor.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/certs"
CONFIG_FILE="${ROOT_DIR}/configs/default/security/mtls.yaml"

mkdir -p "${OUTPUT_DIR}"

echo "[+] Generating root CA"
openssl req -x509 -nodes -newkey rsa:4096 \
  -keyout "${OUTPUT_DIR}/rootCA.key" \
  -out "${OUTPUT_DIR}/rootCA.pem" \
  -days 365 \
  -subj "/CN=opus-gpu-root/O=Opus GPU"

generate_cert() {
  local name="$1"
  local cn="$2"

  local csr_conf="${OUTPUT_DIR}/${name}-csr.conf"
  cat >"${csr_conf}" <<EOF
[ req ]
default_bits       = 4096
prompt             = no
default_md         = sha256
req_extensions     = req_ext
distinguished_name = dn

[ dn ]
CN = ${cn}
O  = Opus GPU

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${name}
DNS.2 = ${name}.internal
IP.1  = 127.0.0.1
EOF

  openssl req -new -keyout "${OUTPUT_DIR}/${name}.key" -nodes \
    -out "${OUTPUT_DIR}/${name}.csr" -config "${csr_conf}"

  cat >"${OUTPUT_DIR}/${name}-cert.conf" <<EOF
[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${name}
DNS.2 = ${name}.internal
IP.1  = 127.0.0.1
EOF

  openssl x509 -req -in "${OUTPUT_DIR}/${name}.csr" \
    -CA "${OUTPUT_DIR}/rootCA.pem" -CAkey "${OUTPUT_DIR}/rootCA.key" \
    -CAcreateserial -out "${OUTPUT_DIR}/${name}.pem" \
    -days 90 -sha256 -extfile "${OUTPUT_DIR}/${name}-cert.conf" -extensions v3_req
}

for svc in control-plane scheduler executor; do
  echo "[+] Issuing certificate for ${svc}"
  generate_cert "${svc}" "${svc}.internal"
done

echo "[+] Certificates stored in ${OUTPUT_DIR}"
