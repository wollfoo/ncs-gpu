# Threat Model

## Assets
- GPU compute clusters
- Control-plane scheduler/API
- Job queue (NATS)

## Threats (STRIDE)
- Spoofing: bắt buộc mTLS và JWT dịch vụ.
- Tampering: ký container bằng cosign, immutable registries.
- Repudiation: log audit qua Loki + Tempo.
- Information Disclosure: Vault secret, no plaintext wallet.
- Denial of Service: Rate limit tại API, backpressure queue.
- Elevation of Privilege: OPA policy, least privilege IAM.
