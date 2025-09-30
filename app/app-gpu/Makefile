# **[Makefile]** (kịch bản build/chạy – tiện ích DevEx)
SHELL := /bin/bash
CARGO ?= cargo

.PHONY: build run-orch run-worker test sbom sign docker-build docker-run

build:
	$(CARGO) build --release

run-orch:
	RUST_LOG=info ORCH_ADDR=0.0.0.0:8080 $(CARGO) run --release --bin orchestrator

run-worker:
	RUST_LOG=info ORCH_URL=http://127.0.0.1:8080 $(CARGO) run --release --bin worker

test:
	$(CARGO) test --all

# **[SBOM]** (hoá đơn vật liệu phần mềm – Syft)
sbom:
	@if command -v syft >/dev/null 2>&1; then \
		syft packages dir:. -o json > sbom.json; echo "SBOM written to sbom.json"; \
	else \
		echo "syft not installed - skip"; \
	fi

# **[Signing]** (ký ảnh – cosign)
sign:
	@if command -v cosign >/dev/null 2>&1; then \
		cosign sign --yes $(IMAGE); \
	else \
		echo "cosign not installed - skip"; \
	fi

docker-build:
	docker build -t api-models:latest -f Dockerfile .

docker-run:
	docker run --rm -it \
		--gpus all \
		--user 1000:1000 \
		--security-opt seccomp=./scripts/seccomp-profile.json \
		-p 8080:8080 api-models:latest orchestrator
