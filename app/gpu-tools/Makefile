# Makefile for OPUS-GPU Tools
# Build automation and development tasks

# ============================================================================
# Variables
# ============================================================================
VERSION ?= dev
BUILD_DATE := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo 'unknown')
LDFLAGS := -s -w -X main.Version=$(VERSION) -X main.BuildDate=$(BUILD_DATE) -X main.GitCommit=$(GIT_COMMIT)

GO := go
GOFLAGS := -v
BINDIR := build/bin
DOCKER_IMAGE := opus-gpu
DOCKER_TAG := $(VERSION)

# ============================================================================
# Default target
# ============================================================================
.PHONY: all
all: clean build

# ============================================================================
# Build targets
# ============================================================================
.PHONY: build
build: build-go build-rust

.PHONY: build-go
build-go: ## Build all Go binaries
	@echo "Building Go tools..."
	@mkdir -p $(BINDIR)
	$(GO) build $(GOFLAGS) -ldflags="$(LDFLAGS)" -o $(BINDIR)/gpu-ctl ./cmd/gpu-ctl
	$(GO) build $(GOFLAGS) -ldflags="$(LDFLAGS)" -o $(BINDIR)/gpu-watchdog ./cmd/gpu-watchdog
	$(GO) build $(GOFLAGS) -ldflags="$(LDFLAGS)" -o $(BINDIR)/metrics-aggregator ./cmd/metrics-aggregator
	@echo "✓ Go binaries built successfully"

.PHONY: build-rust
build-rust: ## Build Rust miner binary
	@echo "Building Rust miner..."
	cd ../app && cargo build --release --bin gpu-miner
	@mkdir -p $(BINDIR)
	cp ../app/target/release/gpu-miner $(BINDIR)/
	@echo "✓ Rust binary built successfully"

.PHONY: build-docker
build-docker: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) -f deploy/docker/Dockerfile.miner ..
	docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest
	@echo "✓ Docker image built successfully"

# ============================================================================
# Test targets
# ============================================================================
.PHONY: test
test: test-go test-rust ## Run all tests

.PHONY: test-go
test-go: ## Run Go tests
	@echo "Running Go tests..."
	$(GO) test -v -race -cover ./...

.PHONY: test-rust
test-rust: ## Run Rust tests
	@echo "Running Rust tests..."
	cd ../app && cargo test --release

.PHONY: test-integration
test-integration: ## Run integration tests
	@echo "Running integration tests..."
	$(GO) test -v -tags=integration ./...

.PHONY: benchmark
benchmark: ## Run benchmarks
	@echo "Running benchmarks..."
	$(GO) test -bench=. -benchmem ./...

# ============================================================================
# Code quality targets
# ============================================================================
.PHONY: lint
lint: ## Run linters
	@echo "Running linters..."
	golangci-lint run ./...
	cd ../app && cargo clippy -- -D warnings

.PHONY: fmt
fmt: ## Format code
	@echo "Formatting code..."
	$(GO) fmt ./...
	cd ../app && cargo fmt

.PHONY: vet
vet: ## Run go vet
	@echo "Running go vet..."
	$(GO) vet ./...

# ============================================================================
# Development targets
# ============================================================================
.PHONY: run-cli
run-cli: ## Run gpu-ctl CLI
	$(GO) run ./cmd/gpu-ctl $(ARGS)

.PHONY: run-watchdog
run-watchdog: ## Run watchdog daemon
	$(GO) run ./cmd/gpu-watchdog

.PHONY: run-aggregator
run-aggregator: ## Run metrics aggregator
	$(GO) run ./cmd/metrics-aggregator

.PHONY: dev
dev: ## Start development environment
	docker-compose -f deploy/docker/docker-compose.yml up

# ============================================================================
# Deployment targets
# ============================================================================
.PHONY: deploy-docker
deploy-docker: ## Deploy với Docker Compose
	./deploy/scripts/deploy.sh docker

.PHONY: deploy-systemd
deploy-systemd: ## Deploy với systemd
	sudo ./deploy/scripts/deploy.sh systemd

.PHONY: deploy-k8s
deploy-k8s: ## Deploy to Kubernetes
	./deploy/scripts/deploy.sh k8s

# ============================================================================
# Protobuf targets
# ============================================================================
.PHONY: proto
proto: ## Generate protobuf code
	@echo "Generating protobuf code..."
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		api/proto/miner.proto

# ============================================================================
# Cleanup targets
# ============================================================================
.PHONY: clean
clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	rm -rf $(BINDIR)
	cd ../app && cargo clean

.PHONY: clean-docker
clean-docker: ## Clean Docker images
	docker rmi -f $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest 2>/dev/null || true

# ============================================================================
# Install targets
# ============================================================================
.PHONY: install
install: build ## Install binaries to /usr/local/bin
	@echo "Installing binaries..."
	sudo cp $(BINDIR)/gpu-ctl /usr/local/bin/
	sudo cp $(BINDIR)/gpu-watchdog /usr/local/bin/
	sudo cp $(BINDIR)/metrics-aggregator /usr/local/bin/
	sudo cp $(BINDIR)/gpu-miner /usr/local/bin/
	@echo "✓ Binaries installed successfully"

.PHONY: uninstall
uninstall: ## Uninstall binaries từ /usr/local/bin
	@echo "Uninstalling binaries..."
	sudo rm -f /usr/local/bin/gpu-ctl
	sudo rm -f /usr/local/bin/gpu-watchdog
	sudo rm -f /usr/local/bin/metrics-aggregator
	sudo rm -f /usr/local/bin/gpu-miner
	@echo "✓ Binaries uninstalled successfully"

# ============================================================================
# Documentation targets
# ============================================================================
.PHONY: docs
docs: ## Generate documentation
	@echo "Generating documentation..."
	godoc -http=:6060

# ============================================================================
# Utility targets
# ============================================================================
.PHONY: version
version: ## Show version information
	@echo "Version:    $(VERSION)"
	@echo "Build date: $(BUILD_DATE)"
	@echo "Git commit: $(GIT_COMMIT)"

.PHONY: deps
deps: ## Download dependencies
	@echo "Downloading Go dependencies..."
	$(GO) mod download
	$(GO) mod verify
	@echo "Downloading Rust dependencies..."
	cd ../app && cargo fetch

.PHONY: tidy
tidy: ## Tidy dependencies
	@echo "Tidying dependencies..."
	$(GO) mod tidy

.PHONY: help
help: ## Show this help message
	@echo "OPUS-GPU Tools - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make build              # Build all binaries"
	@echo "  make test               # Run all tests"
	@echo "  make deploy-docker      # Deploy với Docker Compose"
	@echo "  make run-cli ARGS=status # Run CLI with arguments"

# ============================================================================
# CI/CD targets
# ============================================================================
.PHONY: ci
ci: clean deps lint test build ## CI pipeline

.PHONY: release
release: clean test build build-docker ## Release build
	@echo "Creating release artifacts..."
	@mkdir -p release
	tar -czf release/opus-gpu-$(VERSION)-linux-amd64.tar.gz -C $(BINDIR) .
	@echo "✓ Release artifacts created in release/"

.DEFAULT_GOAL := help
