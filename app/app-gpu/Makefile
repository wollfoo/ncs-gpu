# Makefile cho GPU Mining System v2.0

.PHONY: all build test clean docker-build docker-push deploy

# Biến môi trường
DOCKER_REGISTRY ?= localhost:5000
VERSION ?= 2.0.0
GO_VERSION = 1.22
RUST_VERSION = 1.75

# Build targets
all: build test

build: build-go build-rust

build-go:
	@echo "🔨 Building Go services..."
	cd cmd/api && go build -o ../../bin/api-gateway
	cd cmd/orchestrator && go build -o ../../bin/orchestrator

build-rust:
	@echo "🔨 Building Rust GPU workers..."
	cd cmd/worker && cargo build --release
	cp cmd/worker/target/release/gpu-worker bin/

test:
	@echo "🧪 Running tests..."
	go test ./...
	cd cmd/worker && cargo test

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf bin/
	cd cmd/worker && cargo clean

# Docker operations
docker-build:
	@echo "🐳 Building Docker images..."
	docker build -f deployments/docker/api.Dockerfile -t $(DOCKER_REGISTRY)/gpu-api:$(VERSION) .
	docker build -f deployments/docker/orchestrator.Dockerfile -t $(DOCKER_REGISTRY)/gpu-orchestrator:$(VERSION) .
	docker build -f deployments/docker/worker.Dockerfile -t $(DOCKER_REGISTRY)/gpu-worker:$(VERSION) .

docker-push:
	@echo "📤 Pushing images to registry..."
	docker push $(DOCKER_REGISTRY)/gpu-api:$(VERSION)
	docker push $(DOCKER_REGISTRY)/gpu-orchestrator:$(VERSION)
	docker push $(DOCKER_REGISTRY)/gpu-worker:$(VERSION)

# Deployment
deploy:
	@echo "🚀 Deploying to cluster..."
	kubectl apply -f deployments/k8s/

status:
	@echo "📊 System status:"
	@kubectl get pods -n gpu-mining
	@echo "\n📈 GPU utilization:"
	@nvidia-smi --query-gpu=name,utilization.gpu,temperature.gpu,power.draw --format=csv

# Development helpers
dev:
	@echo "🔧 Starting development environment..."
	docker-compose -f deployments/docker-compose.dev.yml up

logs:
	@echo "📜 Tailing logs..."
	docker-compose logs -f

# Benchmarks
benchmark:
	@echo "⚡ Running performance benchmarks..."
	cd tests/benchmarks && go test -bench=.
	cd cmd/worker && cargo bench

# Security scanning
security-scan:
	@echo "🔒 Running security scan..."
	trivy image $(DOCKER_REGISTRY)/gpu-worker:$(VERSION)
	gosec ./...

.DEFAULT_GOAL := help

help:
	@echo "GPU Mining System v2.0 - Make targets:"
	@echo "  make build          - Build all services"
	@echo "  make test           - Run test suite"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make deploy         - Deploy to Kubernetes"
	@echo "  make dev            - Start development environment"
	@echo "  make benchmark      - Run performance benchmarks"
	@echo "  make security-scan  - Run security scanning"
